async def send(context, message):
    '''
    This function prints a message to stdout and sends it to the context
    '''
    print(message)
    await context.send(message)
