"""
LangGraph graph construction with conditional routing, parallel edges,
remediation engine, and strategic planner.

Flow: supervisor → dependency_analyzer → router → [parallel agents] → critic → remediation → strategic_planner → aggregator → END
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from backend.graph.state import GraphState
from backend.graph.nodes import (
    supervisor_node,
    dependency_node,
    router_node,
    security_agent_node,
    test_agent_node,
    algorithmic_opt_agent_node,
    architecture_agent_node,
    prompt_quality_agent_node,
    critic_node,
    remediation_node,
    strategic_planner_node,
    aggregator_node,
)
from backend.schemas import SkillType


# Map skill → node name
SKILL_NODE_MAP = {
    SkillType.SECURITY: "security_agent",
    SkillType.TESTS: "test_agent",
    SkillType.SPEEDUP: "algorithmic_opt_agent",
    SkillType.ARCHITECTURE: "architecture_agent",
    SkillType.PROMPT_QUALITY: "prompt_quality_agent",
}


def _route_skills(state: GraphState) -> list[str]:
    """Conditional edge: return list of agent node names to run in parallel."""
    skills = state.get("skills_to_run", state.get("selected_skills", []))
    nodes = []
    for skill in skills:
        node_name = SKILL_NODE_MAP.get(skill)
        if node_name:
            nodes.append(node_name)
    return nodes if nodes else ["critic"]


def build_graph() -> StateGraph:
    """
    Build the LangGraph for multi-agent orchestration.

    Flow:
      supervisor → dependency_analyzer → router → [parallel agents] → critic → remediation → strategic_planner → aggregator → END

    The remediation node generates production-ready auto-fixes.
    The strategic planner creates prioritized rollout roadmaps.
    """
    graph = StateGraph(GraphState)

    # Add all nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("dependency_analyzer", dependency_node)
    graph.add_node("router", router_node)
    graph.add_node("security_agent", security_agent_node)
    graph.add_node("test_agent", test_agent_node)
    graph.add_node("algorithmic_opt_agent", algorithmic_opt_agent_node)
    graph.add_node("architecture_agent", architecture_agent_node)
    graph.add_node("prompt_quality_agent", prompt_quality_agent_node)
    graph.add_node("critic", critic_node)
    graph.add_node("remediation", remediation_node)
    graph.add_node("strategic_planner", strategic_planner_node)
    graph.add_node("aggregator", aggregator_node)

    # Entry point
    graph.set_entry_point("supervisor")

    # supervisor → dependency_analyzer → router
    graph.add_edge("supervisor", "dependency_analyzer")
    graph.add_edge("dependency_analyzer", "router")

    # router → conditional parallel fan-out to agents
    graph.add_conditional_edges(
        "router",
        _route_skills,
        {
            "security_agent": "security_agent",
            "test_agent": "test_agent",
            "algorithmic_opt_agent": "algorithmic_opt_agent",
            "architecture_agent": "architecture_agent",
            "prompt_quality_agent": "prompt_quality_agent",
            "critic": "critic",
        },
    )

    # All agents → critic (self-reflection before remediation)
    graph.add_edge("security_agent", "critic")
    graph.add_edge("test_agent", "critic")
    graph.add_edge("algorithmic_opt_agent", "critic")
    graph.add_edge("architecture_agent", "critic")
    graph.add_edge("prompt_quality_agent", "critic")

    # critic → remediation → strategic_planner → aggregator → END
    graph.add_edge("critic", "remediation")
    graph.add_edge("remediation", "strategic_planner")
    graph.add_edge("strategic_planner", "aggregator")
    graph.add_edge("aggregator", END)

    return graph


def compile_graph():
    """Compile the graph for execution."""
    return build_graph().compile()
