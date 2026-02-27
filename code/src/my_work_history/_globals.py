INFO_TYPES: list[str] = [
    "prs_opened",
    "prs_assigned",
    "issues_opened",
    "issues_assigned",
]

ENTITIES_TO_GRAPHQL_QUERY_MAPPING: dict[str, str] = {
    "prs_opened": (
        """
query OpenPRs($user: String!, $date: String!, $first: Int!) {
    search(
        query: "author:$user type:pr created:$date..$date"
        type: ISSUE
        first: $first
    ) {
        edges {
            node {
                ... on PullRequest {
                    url
                }
            }
        }
    }
}
"""
    ),
    "prs_assigned": (
        """
query AssignedPRs($user: String!, $date: String!, $first: Int!) {
    search(
        query: "assignee:$user type:pr assigned:$date..$date"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on PullRequest { url } } }
    }
}
"""
    ),
    "issues_opened": (
        """
query OpenIssues($user: String!, $date: String!, $first: Int!) {
    search(
        query: "author:$user type:issue created:$date..$date"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
    }
}
"""
    ),
    "issues_assigned": (
        """
query AssignedIssues($user: String!, $date: String!, $first: Int!) {
    search(
        query: "assignee:$user type:issue assigned:$date..$date"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
    }
}
"""
    ),
}
