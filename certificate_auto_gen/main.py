from lambda_function import lambda_handler


event = {
    "thingName": "TestUfar",
     "delete":True
}


context = {}


response = lambda_handler(event, context)


print("Lambda Response:")
print(response)
