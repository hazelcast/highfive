from __future__ import absolute_import

from eventhandler import EventHandler


LABEL_NAME = "All Languages Should Check"

CLIENTS = [
    "hazelcast-python-client",
    "hazelcast-nodejs-client",
    "hazelcast-csharp-client",
    "hazelcast-cpp-client",
    "hazelcast-go-client",
]

ISSUE_TITLE = "[TRACKING ISSUE] %s"

ISSUE_BODY = """The tracking issue for the Java side PR.

**%s**

See %s for details.

---

%s
"""


class ClientIssuesHandler(EventHandler):
    def on_issue_labeled(self, api, payload):
        if "pull_request" not in payload:
            return

        pr = payload["pull_request"]
        labels = pr["labels"]

        should_create = False
        for label in labels:
            if label["name"] == LABEL_NAME:
                should_create = True
                break

        if not should_create:
            return

        title = pr["title"]
        html_url = pr["html_url"]
        pr_body = pr["body"]

        issue_title = ISSUE_TITLE % title
        issue_body = ISSUE_BODY % (title, html_url, pr_body)
        for client in CLIENTS:
            api.create_issue(issue_title, issue_body, "hazelcast", client)
