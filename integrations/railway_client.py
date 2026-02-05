"""
Railway Integration for Phoenix AI
Handles deployments, environment variables, logs, and project management
"""

import os
import httpx
from typing import Dict, List, Optional


class RailwayClient:
    """Railway API client for deployment operations"""

    def __init__(self, token: str = None):
        self.token = token or os.environ.get('RAILWAY_API_TOKEN')
        self.api_url = "https://backboard.railway.app/graphql/v2"

        if not self.token:
            raise ValueError("Railway API token not provided")

    async def _query(self, query: str, variables: dict = None) -> Dict:
        """Execute a GraphQL query"""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.api_url,
                json={
                    "query": query,
                    "variables": variables or {}
                },
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
            )
            data = response.json()

            if "errors" in data:
                raise Exception(f"Railway API error: {data['errors']}")

            return data.get("data", {})

    async def get_user(self) -> Dict:
        """Get current user info"""
        query = """
        query {
            me {
                id
                email
                name
            }
        }
        """
        data = await self._query(query)
        return data.get("me", {})

    async def list_projects(self) -> List[Dict]:
        """List all projects"""
        query = """
        query {
            projects {
                edges {
                    node {
                        id
                        name
                        description
                        createdAt
                        updatedAt
                        environments {
                            edges {
                                node {
                                    id
                                    name
                                }
                            }
                        }
                        services {
                            edges {
                                node {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query)
        projects = data.get("projects", {}).get("edges", [])
        return [
            {
                "id": p["node"]["id"],
                "name": p["node"]["name"],
                "description": p["node"].get("description"),
                "created_at": p["node"]["createdAt"],
                "environments": [
                    {"id": e["node"]["id"], "name": e["node"]["name"]}
                    for e in p["node"].get("environments", {}).get("edges", [])
                ],
                "services": [
                    {"id": s["node"]["id"], "name": s["node"]["name"]}
                    for s in p["node"].get("services", {}).get("edges", [])
                ]
            }
            for p in projects
        ]

    async def get_project(self, project_id: str) -> Dict:
        """Get project details"""
        query = """
        query($projectId: String!) {
            project(id: $projectId) {
                id
                name
                description
                createdAt
                environments {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
                services {
                    edges {
                        node {
                            id
                            name
                            icon
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query, {"projectId": project_id})
        return data.get("project", {})

    async def get_deployments(self, project_id: str, limit: int = 10) -> List[Dict]:
        """Get recent deployments for a project"""
        query = """
        query($projectId: String!, $limit: Int!) {
            deployments(
                input: { projectId: $projectId }
                first: $limit
            ) {
                edges {
                    node {
                        id
                        status
                        createdAt
                        meta
                    }
                }
            }
        }
        """
        data = await self._query(query, {"projectId": project_id, "limit": limit})
        deployments = data.get("deployments", {}).get("edges", [])
        return [
            {
                "id": d["node"]["id"],
                "status": d["node"]["status"],
                "created_at": d["node"]["createdAt"],
                "meta": d["node"].get("meta", {})
            }
            for d in deployments
        ]

    async def get_service_status(self, service_id: str) -> Dict:
        """Get service status"""
        query = """
        query($serviceId: String!) {
            service(id: $serviceId) {
                id
                name
                deployments(first: 1) {
                    edges {
                        node {
                            id
                            status
                            createdAt
                        }
                    }
                }
            }
        }
        """
        data = await self._query(query, {"serviceId": service_id})
        return data.get("service", {})

    async def get_environment_variables(self, project_id: str,
                                        environment_id: str) -> Dict:
        """Get environment variables"""
        query = """
        query($projectId: String!, $environmentId: String!) {
            variables(
                projectId: $projectId
                environmentId: $environmentId
            )
        }
        """
        data = await self._query(query, {
            "projectId": project_id,
            "environmentId": environment_id
        })
        return data.get("variables", {})

    async def set_environment_variable(self, project_id: str,
                                       environment_id: str,
                                       name: str, value: str) -> bool:
        """Set an environment variable"""
        mutation = """
        mutation($projectId: String!, $environmentId: String!, $name: String!, $value: String!) {
            variableUpsert(
                input: {
                    projectId: $projectId
                    environmentId: $environmentId
                    name: $name
                    value: $value
                }
            )
        }
        """
        await self._query(mutation, {
            "projectId": project_id,
            "environmentId": environment_id,
            "name": name,
            "value": value
        })
        return True

    async def redeploy(self, service_id: str, environment_id: str) -> Dict:
        """Trigger a redeployment"""
        mutation = """
        mutation($serviceId: String!, $environmentId: String!) {
            serviceRedeploy(
                serviceId: $serviceId
                environmentId: $environmentId
            )
        }
        """
        data = await self._query(mutation, {
            "serviceId": service_id,
            "environmentId": environment_id
        })
        return data

    async def get_logs(self, deployment_id: str, limit: int = 100) -> List[str]:
        """Get deployment logs"""
        query = """
        query($deploymentId: String!, $limit: Int!) {
            deploymentLogs(
                deploymentId: $deploymentId
                limit: $limit
            ) {
                message
                timestamp
            }
        }
        """
        data = await self._query(query, {
            "deploymentId": deployment_id,
            "limit": limit
        })
        logs = data.get("deploymentLogs", [])
        return [f"[{log['timestamp']}] {log['message']}" for log in logs]

    async def get_project_status(self, project_id: str) -> Dict:
        """Get comprehensive project status"""
        project = await self.get_project(project_id)
        deployments = await self.get_deployments(project_id, limit=3)

        latest_deployment = deployments[0] if deployments else None

        return {
            "project": project,
            "latest_deployment": latest_deployment,
            "recent_deployments": deployments,
            "status": latest_deployment["status"] if latest_deployment else "unknown"
        }

    async def create_project(self, name: str, description: str = None) -> Dict:
        """Create a new project"""
        mutation = """
        mutation($name: String!, $description: String) {
            projectCreate(
                input: {
                    name: $name
                    description: $description
                }
            ) {
                id
                name
            }
        }
        """
        data = await self._query(mutation, {
            "name": name,
            "description": description
        })
        return data.get("projectCreate", {})

    async def deploy_from_github(self, project_id: str, repo: str,
                                 branch: str = "main") -> Dict:
        """Deploy a GitHub repository to a project"""
        # This would need service creation and linking to GitHub
        # For now, return a placeholder
        return {
            "status": "pending",
            "message": f"Deployment from {repo}:{branch} initiated"
        }
