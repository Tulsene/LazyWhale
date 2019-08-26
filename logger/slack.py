from utils.singleton import singleton

@singleton
class Slack:
    def auth(self, token, channel, logger):
        self.token = token
        self.channel = channel
        self.logger = logger
        import slack
        self.client = slack.WebClient(self.token)
        self.send_slack_message('Start routine.')

    def send_slack_message(self, message):
        """Send a message to slack channel.
        message: string.
        return: slack object"""
        try:
            message = str(message)
            self.logger.warning(message)
            rsp = self.client.chat_postMessage(
                channel=self.channel,
                text=message)
            if rsp['ok'] is False:
                for item in rsp:
                    raise ValueError(item)
            return rsp
        except Exception as e:
            self.applog.critical(f'Something went wrong with slack: {e}')
            return