generate:
    datamodel-codegen --input src/main/resources/openapi/openapi.yaml \
	--input-file-type openapi \
	--output app/schemas/generated.py \
	--output-model-type pydantic_v2.BaseModel \
	--target-python-version 3.10