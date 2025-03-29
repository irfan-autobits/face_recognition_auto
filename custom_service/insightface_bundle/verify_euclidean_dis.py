import numpy as np
from scipy.spatial.distance import euclidean

# Function to normalize an embedding (L2 normalization)
def normalize(embedding):
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm

# Function to calculate the Euclidean distance
def euclidean_distance(embedding1, embedding2):
    return euclidean(embedding1, embedding2)

# Function to verify the top N closest matches
def verify_identity(input_embedding, known_embeddings, top_n=1):
    # Normalize the input embedding
    input_embedding = normalize(input_embedding)
    
    distances = []
    
    # Calculate the distance for each known embedding
    for emb in known_embeddings:
        known_embedding = normalize(emb['embedding'])
        distance = euclidean_distance(input_embedding, known_embedding)
        
        # Store the distance with the corresponding subject name
        distances.append({
            'subject_name': emb['subject_name'],
            'distance': distance
        })
    
    # Sort the distances by ascending order (smallest distance first)
    distances.sort(key=lambda x: x['distance'])
    
    # Get the top N matches (or as many as possible based on the threshold)
    matches = []
    for i in range(min(top_n, len(distances))):
            matches.append(distances[i])  # Add the match if it's below the threshold
    
    return matches
