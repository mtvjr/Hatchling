async def send(context, message):
    '''
    This function prints a message to stdout and sends it to the context
    '''
    print(message)
    await context.send(message)


def is_from_guild(context):
    """
    This function returns true if a message was sent from a guild, false otherwise.
    """
    return context.message.guild is not None


def is_from_dm(context):
    """
    This function returns true if a message was sent from a direct message, false otherwise.
    """
    return context.message.guild is None
