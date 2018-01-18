from .ldap import parse_scope
from .role import RoleOptions
from .utils import string_types


def acldict(value):
    if not hasattr(value, 'items'):
        raise ValueError('acl_dict must be a dict')

    return value


default_ldap_query = {
    'base': '',
    'filter': '(objectClass=*)',
    'scope': 'sub',
}


def ldapquery(value):
    if not isinstance(value, dict):
        raise ValueError("ldap: is not a dict")

    query = dict(default_ldap_query, **value)
    query['scope'] = parse_scope(query['scope'])

    # Clean value from old manual attribute
    query.pop('attribute', None)

    return query


def acl(raw):
    allowed_keys = set(['grant', 'inspect', 'revoke', 'type'])
    defined_keys = set(raw.keys())
    spurious_keys = defined_keys - allowed_keys

    if spurious_keys:
        msg = "Unknown keys %s" % (', '.join(spurious_keys),)
        raise ValueError(msg)

    raw.setdefault('type', 'nspacl')

    return raw


def acls(raw):
    if not isinstance(raw, dict):
        raise ValueError('acls must be a dict')

    value = {}
    for k, v in raw.items():
        if isinstance(v, list):
            value[k] = v
        elif isinstance(v, dict):
            value[k] = acl(v)
        else:
            msg = "Unknown value %.32s for %s" % (v, k,)
            raise ValueError(msg)
    return value


def rolerule(value):
    rule = value

    if value is None:
        raise ValueError("Empty role rule. Wrong indentation?")

    if isinstance(rule, string_types):
        rule = dict(names=[rule])

    if 'name' in rule:
        rule['names'] = rule.pop('name')
    if 'names' in rule and isinstance(rule['names'], string_types):
        rule['names'] = [rule['names']]

    if 'names' not in rule and 'name_attribute' not in rule:
        raise ValueError("Missing role name")

    if 'parent' in rule:
        rule['parents'] = rule.pop('parent')
    rule.setdefault('parents', [])
    if isinstance(rule['parents'], string_types):
        rule['parents'] = [rule['parents']]

    options = rule.setdefault('options', {})

    if isinstance(options, string_types):
        options = options.split()

    if isinstance(options, list):
        options = dict(
            (o[2:] if o.startswith('NO') else o, not o.startswith('NO'))
            for o in options
        )

    rule['options'] = RoleOptions(**options)
    return rule


def grantrule(value):
    if not isinstance(value, dict):
        raise ValueError('Grant rule must be a dict.')
    if 'acl' not in value:
        raise ValueError('Missing acl to grant rule.')

    allowed_keys = set([
        'acl', 'database', 'schema',
        'role', 'roles', 'role_match', 'role_attribute',
    ])
    defined_keys = set(value.keys())

    if defined_keys - allowed_keys:
        msg = 'Unknown parameter to grant rules: %s' % (
            ', '.join(defined_keys - allowed_keys)
        )
        raise ValueError(msg)

    if 'role' in value:
        value['roles'] = value.pop('role')
    if 'roles' in value and isinstance(value['roles'], string_types):
        value['roles'] = [value['roles']]

    if 'roles' not in value and 'role_attribute' not in value:
        raise ValueError('Missing role in grant rule.')

    return value


def ismapping(value):
    # Check whether a YAML value is supposed to be a single mapping.
    if not isinstance(value, dict):
        return False
    return bool(set(['grant', 'ldap', 'role', 'roles']) >= set(value.keys()))


def gather_queried_attributes(mapping):
    for role in mapping.get('roles', []):
        for k, v in role.items():
            if k.endswith('_attribute'):
                yield v.partition('.')[0]


def mapping(value):
    # A single mapping from a query to a set of role rules. This function
    # translate random YAML to cannonical schema.

    if not isinstance(value, dict):
        raise ValueError("Mapping should be a dict.")

    if 'role' in value:
        value['roles'] = value.pop('role')
    if 'roles' not in value:
        value['roles'] = []
    if not isinstance(value['roles'], list):
        value['roles'] = [value['roles']]

    value['roles'] = [rolerule(r) for r in value['roles']]

    if 'grant' in value:
        if isinstance(value['grant'], dict):
            value['grant'] = [value['grant']]
        value['grant'] = [grantrule(g) for g in value['grant']]

    if not value['roles'] and 'grant' not in value:
        # Don't accept unused LDAP queries.
        raise ValueError("Missing role or grant rule.")

    if 'ldap' in value:
        value['ldap'] = ldapquery(value['ldap'])
        value['ldap']['attributes'] = list(gather_queried_attributes(value))

    return value


def syncmap(value):
    # Validate and translate raw YAML value to cannonical form used internally.
    #
    # A sync map has the following canonical schema:
    #
    # <__all__|dbname>:
    #   <__all__|__any__|schema>:
    #   - ldap: <ldapquery>
    #     roles:
    #     - <rolerule>
    #     - ...
    #   ...
    # ...
    #
    # But we accept a wide variety of shorthand schemas:
    #
    # Single mapping:
    #
    # roles: [<rolerule>]
    #
    # List of mapping:
    #
    # - roles: [<rolerule>]
    # - ...
    #
    # dict of dbname->single mapping
    #
    # appdb:
    #   roles: <rolerule>
    #
    # dict of dbname-> list of mapping
    #
    # appdb:
    # - roles: <rolerule>
    #
    # dict of dbname->schema->single mapping
    #
    # appdb:
    # - roles: <rolerule>
    # dict of dbname->schema->single mapping
    #
    # appdb:
    #   appschema:
    #     roles: <rolerule>

    if not value:
        return {}

    if ismapping(value):
        value = [value]

    if isinstance(value, list):
        value = dict(__all__=value)

    if not isinstance(value, dict):
        raise ValueError("Illegal value for sync_map.")

    for dbname, ivalue in value.items():
        if ismapping(ivalue):
            value[dbname] = ivalue = [ivalue]

        if isinstance(ivalue, list):
            value[dbname] = ivalue = dict(__any__=ivalue)

        for schema, maplist in ivalue.items():
            if isinstance(maplist, dict):
                ivalue[schema] = maplist = [maplist]

            maplist[:] = [mapping(m) for m in maplist]

    return value


def raw(v):
    return v
