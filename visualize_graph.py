import networkx as nx
import matplotlib.pyplot as plt

# Define nodes
nodes = [
    "symptom_collection",
    "diagnosis",
    "exposure_collection",
    "location_collection",
    "bq_submission",
    "care_advice",
    "END"
]

# Define edges (from your graph construction)
edges = [
    ("symptom_collection", "diagnosis"),
    ("symptom_collection", "END"),
    ("diagnosis", "exposure_collection"),
    ("diagnosis", "END"),
    ("exposure_collection", "location_collection"),
    ("exposure_collection", "END"),
    ("location_collection", "bq_submission"),
    ("location_collection", "END"),
    ("bq_submission", "care_advice"),
    ("care_advice", "END")
]

# Build graph
G = nx.DiGraph()
G.add_nodes_from(nodes)
G.add_edges_from(edges)

# Draw
plt.figure(figsize=(10,6))
pos = nx.spring_layout(G, seed=42)  # or nx.planar_layout(G)
nx.draw(G, pos, with_labels=True, node_size=3000, node_color="lightblue", arrowsize=20, font_size=10, font_weight="bold")
plt.show()
