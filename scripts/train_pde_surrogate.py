import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# Add the parent directory to sys.path so we can import the model
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from vanl.backend.core.differentiable_physics import SurrogatePDEModel

def generate_synthetic_data(num_samples=1000):
    """
    Generates synthetic training data for the PDE surrogate.
    Inputs: Q, I, R_int, D_solid, C_rate, cutoff_V
    Outputs: Voltage profile over 500 time steps
    """
    inputs = []
    outputs = []
    
    for _ in range(num_samples):
        Q = np.random.uniform(10.0, 100.0)
        I = np.random.uniform(0.01, 2.0)
        R_int = np.random.uniform(0.01, 0.2)
        D_solid = 10.0 ** np.random.uniform(-14, -10)
        C_rate = np.random.uniform(0.1, 5.0)
        cutoff_V = np.random.uniform(2.0, 3.0)
        
        inputs.append([Q, I, R_int, D_solid, C_rate, cutoff_V])
        
        # Ground truth using our heuristic math from differentiable_physics.py
        # In a real scenario, this would come from a slow SPM numerical solver.
        soc = np.linspace(0.99, 0.01, 500)
        base_v = 3.4
        drop = I * R_int + 0.1 * np.exp(-soc * 5)
        v_pred = base_v - drop - (1 - soc) * 0.5
        
        # Cutoff clipping
        valid_idx = np.where(v_pred >= cutoff_V)[0]
        if len(valid_idx) > 0:
            end_idx = valid_idx[-1] + 1
        else:
            end_idx = 500
            
        # Pad with zeros or repeating last valid value for fixed size output
        v_final = np.zeros(500)
        if end_idx > 0:
            v_final[:end_idx] = v_pred[:end_idx]
            if end_idx < 500:
                v_final[end_idx:] = v_pred[end_idx - 1]
                
        outputs.append(v_final)
        
    return torch.tensor(inputs, dtype=torch.float32), torch.tensor(np.array(outputs), dtype=torch.float32)

def train():
    print("Generating synthetic battery data...")
    X_train, y_train = generate_synthetic_data(5000)
    
    model = SurrogatePDEModel(time_steps=500)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    
    batch_size = 64
    epochs = 50
    
    print(f"Training SurrogatePDEModel for {epochs} epochs...")
    model.train()
    for epoch in range(epochs):
        permutation = torch.randperm(X_train.size()[0])
        epoch_loss = 0.0
        
        for i in range(0, X_train.size()[0], batch_size):
            indices = permutation[i:i+batch_size]
            batch_x, batch_y = X_train[indices], y_train[indices]
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            
        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Loss: {epoch_loss / (X_train.size()[0] / batch_size):.4f}")
            
    # Save the model weights
    save_dir = os.path.join(os.path.dirname(__file__), '..', 'vanl', 'backend', 'ml', 'saved_models')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, 'pde_surrogate.pt')
    
    torch.save(model.state_dict(), save_path)
    print(f"Model saved to {save_path}")

if __name__ == "__main__":
    train()
