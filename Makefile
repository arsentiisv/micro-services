.PHONY: proto
proto:
	python -m grpc_tools.protoc -I./proto --python_out=./flight_service/app/grpc_server --pyi_out=./flight_service/app/grpc_server --grpc_python_out=./flight_service/app/grpc_server ./proto/flight.proto
	python -m grpc_tools.protoc -I./proto --python_out=./booking_service/app/grpc_client --pyi_out=./booking_service/app/grpc_client --grpc_python_out=./booking_service/app/grpc_client ./proto/flight.proto
