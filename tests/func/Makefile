default:

rpm:
	make -C ../../packaging rpm

tests:
	touch bash_history
	docker-compose up --abort-on-container-exit runner

clean:
	make -C ../../packaging clean
	docker-compose down -v

debug:
	docker-compose exec runner /bin/bash