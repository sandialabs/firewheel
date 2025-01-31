from firewheel.control.repository_db import RepositoryDb


def initalize_repo_db():
    repository_db = RepositoryDb(
        db_filename="test_repositories.json",
    )
    for repo in repository_db.list_repositories():
        repository_db.delete_repository(repo)
    return repository_db


def cleanup_repo_db(repository_db):
    for repo in repository_db.list_repositories():
        repository_db.delete_repository(repo)


def compare_graph_structures(a, b):
    if "nodes" not in a or "links" not in a:
        raise ValueError("First structure is not a valid graph structure.")
    if "nodes" not in b or "links" not in b:
        raise ValueError("Second structure is not a valid graph structure.")

    for n in a["nodes"]:
        found = False
        for m in b["nodes"]:
            if n == m:
                found = True
                break
        if not found:
            return False
    for m in b["nodes"]:
        found = False
        for n in a["nodes"]:
            if n == m:
                found = True
                break
        if not found:
            return False

    for n in a["links"]:
        found = False
        for m in b["links"]:
            if n == m:
                found = True
                break
        if not found:
            return False
    for m in b["links"]:
        found = False
        for n in a["links"]:
            if n == m:
                found = True
                break
        if not found:
            return False

    for key in a:
        if key in ("nodes", "links"):
            continue
        try:
            if a[key] != b[key]:
                return False
        except KeyError:
            return False
    for key in b:
        if key in ("nodes", "links"):
            continue
        try:
            # No need to compare here--if the key exists in both a and b, then
            # it will already have been checked in the previous loop checking
            # a's keys. We just want to make sure that the key we found in b
            # also exists in a.
            a[key]
        except KeyError:
            return False

    return True
