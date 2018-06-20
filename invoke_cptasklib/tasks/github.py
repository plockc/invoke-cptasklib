from datetime import datetime
import json
import os
import re

from invoke import task
import requests

from invoke_cptasklib.tasks.file_util import is_dir


with open(os.path.join(os.environ['HOME'],
                       '.config/ccp-github-api-auth-tokens.yml'), 'r') as f:
    auth_tokens = json.load(f)


def _get_remotes(c, repo):
    return c.run("git remote", hide="out").stdout.strip().splitlines()


@task
def get_remotes(c, repo):
    print(_get_remotes(c, repo))


@task
def ensure_remote(c, repo, owner=None, server="github.com"):
    if owner is None:
        owner = os.environ['USER']
    with c.cd(repo):
        if owner not in _get_remotes(c, repo):
            print("Adding remote for {}".format(owner))
            remote_url = "git@{}:{}/{}.git".format(server, owner, repo)
            c.run("git remote add {} {}".format(owner, remote_url), hide="out")
        c.run("git fetch {}".format(owner), hide="out")



@task
def ensure_cloned_repo(
        c, repo, remote="origin", owner=None, server="github.com"):
    if owner is None:
        owner = os.environ['USER']
    if not is_dir(c, repo):
        remote_url = "git@{}:{}/{}.git".format(server, owner, repo)
        c.run("git clone {}".format(remote_url), hide="out")
    with c.cd(repo):
        c.run("git fetch {}".format(remote), hide="out")


@task
def pull(c, repo):
    with c.cd(repo):
        c.run("git pull")


def pr_json(pr, repo, owner, api="https://api.github.com"):
    pr_url_fmt = "/repos/{owner}/{repo}/pulls/{number}"
    pr_url = pr_url_fmt.format(owner=owner, repo=repo, number=pr)
    return get_json(api, api+pr_url)


@task
def get_pr_status(c, pr_id, repo, owner, api="https://api.github.com"):
    status = _get_pr_status(pr_id, repo, owner, api)
    print("{}/{} PR #{} status: {}".format(owner, repo, pr_id, status[0]))
    for s in status[1]:
        print("{}: {}  {}".format(s[0], s[1], s[2]))



@task
def add_pr_comment(
        c, comment, pr_id, repo, owner, api="https://api.github.com"):
    url_fmt = "/repos/{owner}/{repo}/issues/{pr}/comments"
    url = url_fmt.format(owner=owner, repo=repo, pr=pr_id)
    post = dict(body=comment)
    print("Adding comment to {}".format(pr_id))
    post_json(api, api + url, post)


def _get_pr_status(pr_id, repo, owner, api="https://api.github.com"):
    """
    :returns: (state, context, time of state, urls for state)
    """
    sha = pr_json(pr_id, repo, owner, api)['head']['sha']
    url_fmt = "/repos/{owner}/{repo}/commits/{sha}/statuses"
    url = url_fmt.format(owner=owner, repo=repo, sha=sha)
    status_json = get_json(api, api + url)

    if not status_json:
        return None

    contexts = {s['context'] for s in status_json}

    last_statuses = [next(s for s in status_json
                          if s['context'] == c)
                     for c in contexts]

    def filter_statuses(state):
        statuses = [
            (s["context"],
             datetime.strptime(s['updated_at'], "%Y-%m-%dT%H:%M:%SZ"),
             s["target_url"]) for s in last_statuses if s['state'] == state]
        if not statuses:
            return None
        return (state, statuses[0][0], statuses[0][1], statuses)

    failures = filter_statuses('failure')
    pendings = filter_statuses('pending')
    successes = filter_statuses('success')
    return next((n for n in [failures, pendings, successes] if n is not None),
                None)


@task
def ensure_branch(c, branch, repo, remote=None, fork=None, base=None):
    """

    :param fork: used to validate existing remote branch is correct
        using None will assume that there is no fork and branch is on 'remote'
    """
    ensure_cloned_repo(c, repo)

    if remote is not None:
        ensure_remote(c, repo, owner=remote)

    with c.cd(repo):
        branches = c.run("git branch -vv", hide="out").stdout.splitlines()
        branches = (re.match(
            r". ([_\.\-\w]*) +\w* (\[([/_\.\-\w]*)[ \w:]*\])?.*",
            b).groups() for b in branches)

        branches = [(t[0], t[2]) for t in branches]

        # check if there is no local branch, which means we'll create one
        if not any(b for b in branches if b[0] == branch):
            # if there is no remote to track, then create from base
            if remote is None:
                if base is None:
                    base = "master"
                c.run("git checkout {base}".format(base=base), hide="out")
                c.run("git pull".format(base=base), hide="out")
                c.run("git checkout -b {branch}".format(
                    branch=branch, base=base), hide="out")
            # else create remote tracking branch
            else:
                if base is None:
                    base = branch
                c.run("git checkout -b {branch} {remote}/{base}".format(
                    branch=branch, remote=remote, base=base), hide="out")
            return

        # we now know we have a branch of that name already

        # get the remote for the branch
        _, tracked_branch = next(b for b in branches if b[0] == branch)

        # this is a remote base, so default base to the local branch name
        if base is None:
            base = branch

        if fork is None:
            fork = remote

        # check that we are tracking remote properly (if a tracking branch)
        if tracked_branch is None and remote is not None:
            raise Exception("{}, a local branch, is not tracking {}/{}".format(
                branch, fork, base))

        # if it's already created the remote tracking branch is fork/branch
        if tracked_branch is not None and tracked_branch != (
                fork + "/" + branch):
            raise Exception(
                "{} is not tracking {}/{}, it is tracking {}".format(
                    branch, fork, branch, tracked_branch))

        # proper branch is already local, check it out
        c.run("git checkout {}".format(branch), hide="both")


@task
def create_pr(c, title, branch, base_branch, repo, owner, body="",
              fork=None, api="https://api.github.com"):
    url_fmt = "/repos/{owner}/{repo}/pulls"
    url = url_fmt.format(owner=owner, repo=repo)
    if fork is None:
        fork = owner
    post = dict(title=title, head=fork+':'+branch, base=base_branch, body=body)
    print("Creating PR")
    pr_data = post_json(api, api + url, post)
    print(pr_data['html_url'])
    return pr_data['number']


def _get_shas(repo, branch="master", owner=None, api="https://api.github.com"):
    if owner is None:
        owner = os.environ['USER']
    url = ("{api}/repos/{owner}/{repo}/commits?sha={branch}"
           "&per_page=100").format(
            api=api, owner=owner, repo=repo, branch=branch)

    commits_json = get_json(api, url)
    return [c['sha'][:7] for c in commits_json]


@task
def get_shas(c, repo, branch="master", owner=None,
             api="https://api.github.com"):
    print(get_shas(repo, branch, owner, api))


def post_json(api, url, data):
    headers = {'Authorization': "token " + auth_tokens[api]}
    resp = requests.post(url, headers=headers, data=json.dumps(data))
    resp_json = resp.json()
    resp.close()
    return resp_json


def get_json(api, url):
    headers = {'Authorization': "token " + auth_tokens[api]}
    resp = requests.get(url, headers=headers)
    resp_json = resp.json()
    resp.close()
    return resp_json
