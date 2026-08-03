"""Render a self-contained graph view inside Streamlit."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st


def _graph_html(graph: dict[str, Any]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    return f"""
    <div id="graph-root" style="width:100%;height:680px;border:1px solid #d0d7de;border-radius:12px;overflow:hidden;background:#f8fafc;padding:12px;box-sizing:border-box;"></div>
    <script type="text/javascript">
      const nodes = {nodes_json};
      const edges = {edges_json};
      const container = document.getElementById('graph-root');
      const width = container.clientWidth || 900;
      const height = container.clientHeight || 680;

      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', '100%');
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      container.innerHTML = '';
      container.appendChild(svg);

      const categoryColors = {{
        Projects: '#22c55e',
        Areas: '#3b82f6',
        Resources: '#f59e0b',
        Archives: '#64748b'
      }};

      const positions = [];
      const count = nodes.length;
      if (count > 0) {{
        for (let i = 0; i < count; i += 1) {{
          const angle = (i / count) * 2 * Math.PI;
          const radius = Math.min(width, height) * 0.3;
          positions.push({{
            x: width / 2 + Math.cos(angle) * radius,
            y: height / 2 + Math.sin(angle) * radius
          }});
        }}
      }}

      const edgeLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      svg.appendChild(edgeLayer);

      edges.forEach((edge) => {{
        const source = nodes.find((node) => node.id === edge.source);
        const target = nodes.find((node) => node.id === edge.target);
        if (!source || !target) return;
        const start = positions[nodes.indexOf(source)] || {{ x: width / 2, y: height / 2 }};
        const end = positions[nodes.indexOf(target)] || {{ x: width / 2, y: height / 2 }};
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', start.x);
        line.setAttribute('y1', start.y);
        line.setAttribute('x2', end.x);
        line.setAttribute('y2', end.y);
        line.setAttribute('stroke', '#94a3b8');
        line.setAttribute('stroke-width', '1.5');
        line.setAttribute('stroke-opacity', '0.7');
        edgeLayer.appendChild(line);
      }});

      const nodeLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      svg.appendChild(nodeLayer);

      nodes.forEach((node, index) => {{
        const position = positions[index] || {{ x: width / 2, y: height / 2 }};
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', position.x);
        circle.setAttribute('cy', position.y);
        circle.setAttribute('r', 18);
        circle.setAttribute('fill', categoryColors[node.category] || '#8b5cf6');
        circle.setAttribute('stroke', '#1e293b');
        circle.setAttribute('stroke-width', '1.5');
        circle.setAttribute('title', `${{node.label || node.slug || node.id}}\\n${{node.summary || node.preview || ''}}`);
        circle.addEventListener('mouseenter', () => {{
          circle.setAttribute('r', 22);
        }});
        circle.addEventListener('mouseleave', () => {{
          circle.setAttribute('r', 18);
        }});
        nodeLayer.appendChild(circle);

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', position.x);
        label.setAttribute('y', position.y + 32);
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('font-size', '12');
        label.setAttribute('fill', '#0f172a');
        label.textContent = node.label || node.slug || node.id;
        nodeLayer.appendChild(label);
      }});
    </script>
    """


def render_graph(graph: dict[str, Any]) -> None:
    """Render a graph with category-based colors and hover hints."""
    if not graph.get("nodes"):
        st.info("No wiki notes available yet. Generate a graph by running the graph builder.")
        return

    st.components.v1.html(_graph_html(graph), height=720)
