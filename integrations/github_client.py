"""
GitHub Integration for Phoenix AI
Handles all GitHub operations: repos, files, commits, PRs
"""

import os
import base64
from typing import Dict, List, Optional
from github import Github, GithubException


class GitHubClient:
    """GitHub API client for code operations"""

    def __init__(self, token: str = None, default_owner: str = None):
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.default_owner = default_owner or os.environ.get('GITHUB_DEFAULT_OWNER')

        if not self.token:
            raise ValueError("GitHub token not provided")

        self.client = Github(self.token)
        self.user = self.client.get_user()

    def list_repos(self, limit: int = 10) -> List[Dict]:
        """List user's repositories"""
        repos = []
        for repo in self.user.get_repos(sort='updated')[:limit]:
            repos.append({
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description,
                'url': repo.html_url,
                'private': repo.private,
                'default_branch': repo.default_branch,
                'updated_at': repo.updated_at.isoformat()
            })
        return repos

    def get_repo(self, repo_name: str):
        """Get a repository by name"""
        if '/' not in repo_name:
            repo_name = f"{self.default_owner}/{repo_name}"
        return self.client.get_repo(repo_name)

    def create_repo(self, name: str, description: str = "",
                   private: bool = False) -> Dict:
        """Create a new repository"""
        repo = self.user.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=True  # Create with README
        )
        return {
            'name': repo.name,
            'full_name': repo.full_name,
            'html_url': repo.html_url,
            'clone_url': repo.clone_url,
            'default_branch': repo.default_branch
        }

    def get_file_content(self, repo_name: str, path: str,
                        branch: str = None) -> str:
        """Read a file from a repository"""
        repo = self.get_repo(repo_name)
        branch = branch or repo.default_branch

        try:
            content = repo.get_contents(path, ref=branch)
            if isinstance(content, list):
                return f"Path is a directory with {len(content)} files"
            return base64.b64decode(content.content).decode('utf-8')
        except GithubException as e:
            if e.status == 404:
                return f"File not found: {path}"
            raise

    def write_file(self, repo_name: str, path: str, content: str,
                  message: str, branch: str = None) -> Dict:
        """Write or update a file in a repository"""
        repo = self.get_repo(repo_name)
        branch = branch or repo.default_branch

        try:
            # Check if file exists
            existing = repo.get_contents(path, ref=branch)
            # Update existing file
            result = repo.update_file(
                path=path,
                message=message,
                content=content,
                sha=existing.sha,
                branch=branch
            )
        except GithubException as e:
            if e.status == 404:
                # Create new file
                result = repo.create_file(
                    path=path,
                    message=message,
                    content=content,
                    branch=branch
                )
            else:
                raise

        return {
            'commit_sha': result['commit'].sha,
            'commit_url': result['commit'].html_url
        }

    def list_files(self, repo_name: str, path: str = "",
                  branch: str = None) -> List[Dict]:
        """List files in a directory"""
        repo = self.get_repo(repo_name)
        branch = branch or repo.default_branch

        contents = repo.get_contents(path, ref=branch)
        if not isinstance(contents, list):
            contents = [contents]

        return [
            {
                'name': item.name,
                'path': item.path,
                'type': item.type,  # 'file' or 'dir'
                'size': item.size if item.type == 'file' else None
            }
            for item in contents
        ]

    def create_branch(self, repo_name: str, branch_name: str,
                     from_branch: str = None) -> Dict:
        """Create a new branch"""
        repo = self.get_repo(repo_name)
        from_branch = from_branch or repo.default_branch

        # Get the SHA of the source branch
        source = repo.get_branch(from_branch)
        sha = source.commit.sha

        # Create the new branch
        ref = repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=sha
        )

        return {
            'branch': branch_name,
            'sha': sha
        }

    def create_pull_request(self, repo_name: str, title: str, body: str,
                           head: str, base: str = None) -> Dict:
        """Create a pull request"""
        repo = self.get_repo(repo_name)
        base = base or repo.default_branch

        pr = repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base
        )

        return {
            'number': pr.number,
            'url': pr.html_url,
            'state': pr.state
        }

    def get_commits(self, repo_name: str, branch: str = None,
                   limit: int = 10) -> List[Dict]:
        """Get recent commits"""
        repo = self.get_repo(repo_name)
        branch = branch or repo.default_branch

        commits = []
        for commit in repo.get_commits(sha=branch)[:limit]:
            commits.append({
                'sha': commit.sha[:7],
                'message': commit.commit.message.split('\n')[0],
                'author': commit.commit.author.name,
                'date': commit.commit.author.date.isoformat()
            })
        return commits

    def delete_file(self, repo_name: str, path: str, message: str,
                   branch: str = None) -> Dict:
        """Delete a file from repository"""
        repo = self.get_repo(repo_name)
        branch = branch or repo.default_branch

        content = repo.get_contents(path, ref=branch)
        result = repo.delete_file(
            path=path,
            message=message,
            sha=content.sha,
            branch=branch
        )

        return {
            'commit_sha': result['commit'].sha
        }

    def get_repo_info(self, repo_name: str) -> Dict:
        """Get detailed repository information"""
        repo = self.get_repo(repo_name)

        return {
            'name': repo.name,
            'full_name': repo.full_name,
            'description': repo.description,
            'url': repo.html_url,
            'clone_url': repo.clone_url,
            'private': repo.private,
            'default_branch': repo.default_branch,
            'language': repo.language,
            'created_at': repo.created_at.isoformat(),
            'updated_at': repo.updated_at.isoformat(),
            'size': repo.size,
            'stars': repo.stargazers_count,
            'forks': repo.forks_count
        }
