import json
import requests
from utils.singleton import singleton

class Slack():
    # def auth(self, token, channel, logger):
    #     self.token = token
    #     self.channel = channel
    #     self.logger = logger
    #     self.client = None
    #     # import slack
    #     # self.client = slack.WebClient(self.token)
    #     # self.send_slack_message('Start routine.')
    #
    # def send_slack_message(self, message):
    #     """Send a message to slack channel.
    #     message: string.
    #     return: slack object"""
    #     try:
    #         message = str(message)
    #         self.logger.warning(message)
    #         rsp = self.client.chat_postMessage(
    #             channel=self.channel,
    #             text=message)
    #         if rsp['ok'] is False:
    #             for item in rsp:
    #                 raise ValueError(item)
    #         return rsp
    #     except Exception as e:
    #         self.logger.critical(f'Something went wrong with slack: {e}')
    #         return
    def __init__(self, webhook_url):
        self.webhook_url = self.webhook_check(webhook_url)

    def webhook_check(self, webhook_url):
        """Check the webhook url consistence before storing it globaly.
        See https://api.slack.com/tutorials/slack-apps-hello-world to get more
        informatoins about slack webhook.
        :webhook_url: string, delivered by slack.
        :return: string,the webhook url with it's formating checked."""
        url_start = 'https://hooks.slack.com/services/'
        if webhook_url[:33] != url_start:
            raise ValueError(
                f'The beginning of Webhook URL {webhook_url} does not match '
                f'with {url_start}')
        if webhook_url.count('/') != 6:
            raise ValueError(f'{webhook_url} is not a valid webhook url')
        return webhook_url

    def send_slack_message(self, message):
        """Post a message to slack through an incoming webhook.
        :message: string, the message that will be send to slack.
        response: request response object."""
        data = json.dumps(str(message))
        response = requests.post(self.webhook_url,
                                 json={"text": data},
                                 headers={'Content-Type': 'application/json'})

        if response.status_code != 200:
            raise ValueError(
                'Request to slack returned an error %s, the response is:\n%s'
                % (response.status_code, response.text))

        return response