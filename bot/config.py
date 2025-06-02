class BotConfig:
    """Config for Bot"""

    def __init__(self, admin_ids: list, welcome_message: str) -> None:
        self.admin_ids = admin_ids
        self.welcome_message = welcome_message

