import configparser
import datetime
import flask
import hashlib
import hmac
import json
import base64

from waitress import serve
from handlers.assign_reviewer import AssignReviewerHandler

from newpr import GithubAPIProvider


def create_app():
    app = flask.Flask(__name__)

    handler = AssignReviewerHandler()

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

        #if 'payload' in flask.request.form:
        #    expected = hmac.new(webhook_secret.encode("utf-8"), digestmod=hashlib.sha1)
        #    expected.update(raw_data)
        #    expected = expected.hexdigest()
        #    if not hmac.compare_digest('sha1='+expected, signature):
        #        return 'Error: invalid signature\n', 403

        try:
            payload = json.loads(flask.request.form['payload'])
        except (KeyError, ValueError):
            return 'Error: missing or invalid payload\n', 400
        try:
            handler.handle_payload(GithubAPIProvider(payload, user, token), payload)
            return 'OK', 200
        except Exception as e:
            print()
            print('An exception occured while processing a webhook!')
            print('Time:', datetime.datetime.now())
            print('Delivery ID:', delivery)
            print('Event name:', event)
            print('Payload:', json.dumps(payload))
            print(e)
            return 'Internal server error\n', 500

    @app.route('/build', methods=['POST'])
    def build_result():
        try:
            payload = json.loads(flask.request.get_data(), strict=False)
            payload['action'] = 'created'
            payload['repository'] = {
                'owner': {
                    'login': 'hazelcast'
                },
                'name': 'hazelcast',
            }
            payload['issue'] = {
                    'number': payload['id'],
            }
            provider = GithubAPIProvider(payload, user, token)
            provider.post_failure_comment(payload['build-log-url'], payload['artifacts-url'], payload['details'])
            return 'OK', 200
        except Exception as e:
            print(e)
            return 'Internal server error', 400

    @app.route('/')
    def root():
        return 'High Five!', 200

    return app


if __name__ == "__main__":
    serve(create_app(), host='0.0.0.0', port=8000)
