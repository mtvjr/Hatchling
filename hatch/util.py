async def send(message, context):
    '''
    This function prints a message to stdout and sends it to the context
    '''
    print(message)
    await context.send(message)
