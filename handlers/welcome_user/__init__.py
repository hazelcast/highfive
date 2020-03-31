from __future__ import absolute_import

from eventhandler import EventHandler

WELCOME_MSG = ("Thanks for the pull request, and welcome! "
               "The Hazelcast team is excited to review your changes, "
               "and you should hear from @%s or @%s (or someone else) soon. "
               "In the meantime, make sure that you signed the CLA "
               "as described "
               "[here](https://hazelcast.atlassian.net/wiki/spaces/COM/pages/6357071/Hazelcast+Contributor+Agreement).")


class WelcomeUserHandler(EventHandler):
    def on_pr_opened(self, api, payload):
        pr = payload["pull_request"]
        # Add welcome message for new contributors.
        author = pr['user']['login']
        if not api.is_in_the_organization(author):
            # api.post_comment(WELCOME_MSG % ('Holmistr', 'mmedenjak'))
            api.add_label('Source: Community')


handler_interface = WelcomeUserHandler
