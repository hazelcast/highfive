import configparser
import hashlib
import hmac
import json
from logging.config import dictConfig

import flask
from waitress import serve

from handlers.welcome_user import WelcomeUserHandler
from newpr import GithubAPIProvider, handle_payload


def create_app():
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'file.handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': 'server.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB

        }},
        'root': {
            'level': 'INFO',
            'handlers': ['file.handler']
        }
    })

    app = flask.Flask(__name__)

    config = configparser.RawConfigParser()
    config.read('./config')
    user = config.get('github', 'user')
    token = config.get('github', 'token')
    webhook_secret = config.get('github', 'webhook_secret')

    @app.route('/webhook', methods=['POST'])
    def webhook():
        raw_data = flask.request.get_data()

        # Load all the headers
        try:
            event = str(flask.request.headers['X-GitHub-Event'])
            delivery = str(flask.request.headers['X-GitHub-Delivery'])
            signature = str(flask.request.headers['X-Hub-Signature'])
        except KeyError:
            return 'Error: some required webhook headers are missing\n', 400

        if 'payload' in flask.request.form:
            expected = hmac.new(webhook_secret.encode('utf8'), digestmod=hashlib.sha1)
            expected.update(raw_data)
            expected = expected.hexdigest()
            if not hmac.compare_digest('sha1=' + expected, signature):
                return 'Error: invalid signature\n', 403

        try:
            payload = json.loads(flask.request.form['payload'], strict=False)
        except (KeyError, ValueError):
            return 'Error: missing or invalid payload\n', 400
        try:
            api_provider = GithubAPIProvider(payload, user, token)
            api_provider.extract_globals(payload)
            handle_payload(api_provider, payload, [WelcomeUserHandler()])
            return 'OK\n', 200
        except Exception as e:
            app.logger.error('An exception occurred while processing a web hook. Delivery id: {}, event name: {}'
                             .format(delivery, event))
            app.log_exception(e)
            return 'Internal server error\n', 500

    @app.route('/build', methods=['POST'])
    def build_result():
        try:
            payload = json.loads(flask.request.get_data(), strict=False)
            provider = GithubAPIProvider(payload, user, token, 'hazelcast', payload['repo'], payload['id'])
            provider.post_failure_comment(payload['job-name'], payload['build-log-url'], payload['artifacts-url'],
                                          payload['details'])
            return 'OK\n', 200
        except Exception as e:
            app.log_exception(e)
            return 'Something went wrong\n', 400

    @app.route('/')
    def root():
        return 'High Five!\n', 200

    return app


if __name__ == "__main__":
    serve(create_app(), host='0.0.0.0', port=8000)
