from lambda_function import lambda_handler


event = {
    "thingName": "ArnoTest2"  
}


context = {}


response = lambda_handler(event, context)


print("Lambda Response:")
print(response)
