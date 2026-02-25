import my_work_history


def test_fetch_info() -> None:
    test_issues = my_work_history.fetch_info(
        start_date="2026-01-04",
        end_date="2026-01-06",
        username="codycbakerphd",
    )
    expected_issues = {
        "575ca719383a62db400a8e2b353d5c1482322c13": {
            "total_count": 1,
            "incomplete_results": False,
            "items": [
                {
                    "url": "https://api.github.com/repos/con/nwb2bids/issues/252",
                    "repository_url": "https://api.github.com/repos/con/nwb2bids",
                    "labels_url": "https://api.github.com/repos/con/nwb2bids/issues/252/labels{/name}",
                    "comments_url": "https://api.github.com/repos/con/nwb2bids/issues/252/comments",
                    "events_url": "https://api.github.com/repos/con/nwb2bids/issues/252/events",
                    "html_url": "https://github.com/con/nwb2bids/issues/252",
                    "id": 3782320956,
                    "node_id": "I_kwDOLaBElc7hcaM8",
                    "number": 252,
                    "title": "Investigate: run time on 000008",
                    "user": {
                        "login": "CodyCBakerPhD",
                        "id": 51133164,
                        "node_id": "MDQ6VXNlcjUxMTMzMTY0",
                        "avatar_url": "https://avatars.githubusercontent.com/u/51133164?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/CodyCBakerPhD",
                        "html_url": "https://github.com/CodyCBakerPhD",
                        "followers_url": "https://api.github.com/users/CodyCBakerPhD/followers",
                        "following_url": "https://api.github.com/users/CodyCBakerPhD/following{/other_user}",
                        "gists_url": "https://api.github.com/users/CodyCBakerPhD/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/CodyCBakerPhD/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/CodyCBakerPhD/subscriptions",
                        "organizations_url": "https://api.github.com/users/CodyCBakerPhD/orgs",
                        "repos_url": "https://api.github.com/users/CodyCBakerPhD/repos",
                        "events_url": "https://api.github.com/users/CodyCBakerPhD/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/CodyCBakerPhD/received_events",
                        "type": "User",
                        "user_view_type": "public",
                        "site_admin": False,
                    },
                    "labels": [
                        {
                            "id": 9462365404,
                            "node_id": "LA_kwDOLaBElc8AAAACNAA83A",
                            "url": "https://api.github.com/repos/con/nwb2bids/labels/performance",
                            "name": "performance",
                            "color": "f4b2d8",
                            "default": False,
                            "description": "Improve performance of an existing feature",
                        }
                    ],
                    "state": "open",
                    "locked": False,
                    "assignees": [],
                    "milestone": None,
                    "comments": 1,
                    "created_at": "2026-01-05T17:36:59Z",
                    "updated_at": "2026-01-26T15:26:58Z",
                    "closed_at": None,
                    "assignee": None,
                    "author_association": "COLLABORATOR",
                    "type": {
                        "id": 1706307,
                        "node_id": "IT_kwDOAMredc4AGglD",
                        "name": "Task",
                        "description": "A specific piece of work",
                        "color": "yellow",
                        "created_at": "2024-01-25T14:25:30Z",
                        "updated_at": "2024-07-26T10:29:52Z",
                        "is_enabled": True,
                    },
                    "active_lock_reason": None,
                    "sub_issues_summary": {"total": 0, "completed": 0, "percent_completed": 0},
                    "issue_dependencies_summary": {
                        "blocked_by": 0,
                        "total_blocked_by": 0,
                        "blocking": 0,
                        "total_blocking": 0,
                    },
                    "body": (
                        "@asmacdo noted that `nwb2bids` takes a long time to run on Dandiset 000008\n\n"
                        "Should investigate why"
                    ),
                    "reactions": {
                        "url": "https://api.github.com/repos/con/nwb2bids/issues/252/reactions",
                        "total_count": 0,
                        "+1": 0,
                        "-1": 0,
                        "laugh": 0,
                        "hooray": 0,
                        "confused": 0,
                        "heart": 0,
                        "rocket": 0,
                        "eyes": 0,
                    },
                    "timeline_url": "https://api.github.com/repos/con/nwb2bids/issues/252/timeline",
                    "performed_via_github_app": None,
                    "state_reason": None,
                    "pinned_comment": None,
                    "score": 1.0,
                }
            ],
        }
    }
    assert test_issues == expected_issues
