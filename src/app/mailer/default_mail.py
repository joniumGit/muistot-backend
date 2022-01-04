from . import Mailer


class DefaultMailer(Mailer):

    async def send_verify_email(self, username: str, email: str) -> bool:
        pass

    async def verify_email(self, email: str) -> bool:
        pass
