#!/usr/bin/env python3
import json
import zlib
from base64 import standard_b64encode

import requests
from requests.exceptions import HTTPError

import eventhandler
from helpers import is_addition, normalize_file_path

DIFF_HEADER_PREFIX = 'diff --git '


class GithubAPIProvider:
    BASE_URL = "https://api.github.com/"
    contributors_url = BASE_URL + "repos/%s/%s/contributors?per_page=400"
    post_comment_url = BASE_URL + "repos/%s/%s/issues/%s/comments"
    collaborators_url = BASE_URL + "repos/%s/%s/collaborators"
    issue_url = BASE_URL + "repos/%s/%s/issues"
    get_label_url = BASE_URL + "repos/%s/%s/issues/%s/labels"
    add_label_url = BASE_URL + "repos/%s/%s/issues/%s/labels"
    remove_label_url = BASE_URL + "%repos/s/%s/issues/%s/labels/%s"
    check_membership_url = BASE_URL + 'orgs/%s/members/%s'

    def __init__(self, payload, user, token, owner=None, repo=None, issue=None):
        self.owner = owner
        self.repo = repo
        self.issue = issue
        self.user = user
        self.changed_files = None
        self.token = token
        self._labels = None
        self._diff = None
        if "pull_request" in payload:
            self.diff_url = payload["pull_request"]["diff_url"]
            self.pull_url = payload["pull_request"]["url"]

    def extract_globals(self, payload):
        self.owner, self.repo, self.issue = extract_globals_from_payload(payload)

    def api_req(self, method, url, data=None, media_type=None):
        data = None if not data else json.dumps(data)
        headers = {} if not data else {'Content-Type': 'application/json'}

        if self.token:
            authorization = '%s:%s' % (self.user, self.token)
            base64string = standard_b64encode(bytes(authorization.replace('\n', ''), encoding='utf8'))
            headers["Authorization"] = "Basic %s" % base64string.decode('utf8')

        if media_type:
            headers["Accept"] = media_type

        res = getattr(requests, method.lower())(url, data=data, headers=headers)

        if res.headers.get('Content-Encoding'.lower()) == 'gzip':
            try:
                body = zlib.decompress(res.content, 16 + zlib.MAX_WBITS)
            except:
                body = res.text
        else:
            body = res.text

        return {"header": res.headers, "body": body}

    def post_failure_comment(self, job_name, build_log_url, artifacts_url,  details):
#        msg = """The job `{0}` of your PR failed ([log]({1}), [artifacts]({2})).
#Through arcane magic we have determined that the following fragments from the build log may contain information about the problem.
#<details>
#<summary>Click to expand the log file</summary>
#<pre>
#{3}
#</details>
#</pre>""".format(job_name, build_log_url, artifacts_url, details)
        msg = """The job `{0}` of your PR failed.
Through arcane magic we have determined that the following fragments from the build log may contain information about the problem.
<details>
<summary>Click to expand the log file</summary>
<pre>
{3}
</pre>
</details>""".format(job_name, build_log_url, artifacts_url, details)

        self.post_comment(msg)

    # This function is adapted from https://github.com/kennethreitz/requests/blob/209a871b638f85e2c61966f82e547377ed4260d9/requests/utils.py#L562  # noqa
    # Licensed under Apache 2.0: http://www.apache.org/licenses/LICENSE-2.0
    def parse_header_links(self, value):
        if not value:
            return None

        links = {}
        replace_chars = " '\""
        for val in value.split(","):
            try:
                url, params = val.split(";", 1)
            except ValueError:
                url, params = val, ''

            url = url.strip("<> '\"")

            for param in params.split(";"):
                try:
                    key, value = param.split("=")
                except ValueError:
                    break
                key = key.strip(replace_chars)
                if key == 'rel':
                    links[value.strip(replace_chars)] = url

        return links

    def is_in_the_organization(self, username):
        url = self.check_membership_url % (self.owner, username)
        res = self.api_req("GET", url)
        return res['header']['Status'] != '404 Not Found'

    def post_comment(self, body):
        url = self.post_comment_url % (self.owner, self.repo, self.issue)
        try:
            self.api_req("POST", url, {"body": body})
        except HTTPError as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 201:
                pass
            else:
                raise e

    def add_label(self, label):
        url = self.add_label_url % (self.owner, self.repo, self.issue)
        if self._labels:
            self._labels += [label]
        try:
            self.api_req("POST", url, [label])
        except HTTPError as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 201:
                pass
            else:
                raise e

    def remove_label(self, label):
        url = self.remove_label_url % (self.owner, self.repo, self.issue,
                                       label)
        if self._labels and label in self._labels:
            self._labels.remove(label)
        try:
            self.api_req("DELETE", url, {})
        except HTTPError:
            pass

    def get_labels(self):
        url = self.get_label_url % (self.owner, self.repo, self.issue)
        if self._labels is not None:
            return self._labels
        try:
            result = self.api_req("GET", url)
        except HTTPError as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 201:
                pass
            else:
                raise e
        self._labels = map(lambda x: x["name"], json.loads(result['body']))
        return self._labels

    def get_diff(self):
        if self._diff:
            return self._diff
        self._diff = self.api_req("GET", self.diff_url)['body']
        return self._diff

    def set_assignee(self, assignee):
        url = (self.issue_url % (self.owner, self.repo)) + "/" + self.issue
        try:
            self.api_req("PATCH", url, {"assignee": assignee})['body']
        except HTTPError as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 201:
                pass
            else:
                raise e

    def get_pull(self):
        return self.api_req("GET", self.pull_url)["body"]

    def get_diff_headers(self):
        diff = self.get_diff()
        for line in diff.splitlines():
            if line.startswith(DIFF_HEADER_PREFIX):
                yield line

    def get_changed_files(self):
        if self.changed_files is None:
            changed_files = []
            for line in self.get_diff_headers():
                files = line.split(DIFF_HEADER_PREFIX)[-1].split(' ')
                changed_files.extend(files)

            # And get unique values using `set()`
            normalized = map(normalize_file_path, changed_files)
            self.changed_files = set(f for f in normalized if f is not None)
        return self.changed_files

    def get_added_lines(self):
        diff = self.get_diff()
        for line in diff.splitlines():
            if is_addition(line):
                # prefix of one or two pluses (+)
                yield line

    def create_issue(self, title, body, owner=None, repo=None):
        owner = owner or self.owner
        repo = repo or self.repo

        url = self.issue_url % (owner, repo)
        try:
            self.api_req("POST", url, {"title": title, "body": body})
        except HTTPError as e:
            if hasattr(e.response, 'status_code') and e.response.status_code == 201:
                pass
            else:
                raise e


def extract_globals_from_payload(payload):
    if payload["action"] == "created" or payload["action"] == "labeled":
        owner = payload['repository']['owner']['login']
        repo = payload['repository']['name']
        try:
            issue = str(payload['issue']['number'])
        except KeyError:
            issue = str(payload['number'])
    else:
        owner = payload['pull_request']['base']['repo']['owner']['login']
        repo = payload['pull_request']['base']['repo']['name']
        issue = str(payload["number"])
    return owner, repo, issue


img = ('<img src="http://www.joshmatthews.net/warning.svg" '
       'alt="warning" height=20>')
warning_header = '{} **Warning** {}'.format(img, img)
warning_summary = warning_header + '\n\n%s'


def handle_payload(api, payload, handlers=None):
    if not handlers:
        modules, handlers = eventhandler.get_handlers()
    for handler in handlers:
        handler.handle_payload(api, payload)
    warnings = eventhandler.get_warnings()
    if warnings:
        formatted_warnings = '\n'.join(map(lambda x: '* ' + x, warnings))
        api.post_comment(warning_summary % formatted_warnings)
