import datasets
import torch
import numpy as np
from safetensors.torch import save
from snappy import compress
import os
from tqdm import tqdm
#Pillow

def main():
    # --- CONFIGURATION ---
    data_dir = "data/imagenet_gan_128"
    os.makedirs(data_dir, exist_ok=True)
    
    # Format: (Width, Height) because PIL uses (W, H)
    SIZE = (128, 128) 
    SLICE_SIZE = 2048
    
    # --- HELPER: FLUSH TO DISK ---
    def flush_buffer(images, labels, slice_count):
        """Writes the current buffer to disk and clears it."""
    
        # 1. Stack and Convert
        # List of (H, W, 3) -> Tensor (N, 3, H, W)
        # converting to uint8 saves massive space/time
        batch_tensor = torch.from_numpy(np.stack(images)).permute(0, 3, 1, 2).contiguous()
        label_tensor = torch.tensor(labels, dtype=torch.int64)
        
        # 2. Determine Filename
        # User requested: train_{h}_{w}_{slice_count}
        filename = os.path.join(data_dir, f"train_{slice_count}_safetensor.snappy")
        
        # 3. Save
        # If you need snappy output, use this instead:
        with open(filename, "wb") as f:
            f.write(compress(save({"images": batch_tensor, "labels": label_tensor})))

    
    # --- MAIN LOOP ---
    # streaming=True ensures we process one sample at a time without loading everything
    print("Loading streaming dataset...")
    ds = datasets.load_dataset("ILSVRC/imagenet-1k", split="train", streaming=True, token="...")

    # State Management
    images = []
    labels = []
    slice_count = 0
    
    print("Starting iteration...")
    for i, sample in tqdm(enumerate(ds), total=1281167): # Total count for ImageNet Train
        image = sample['image']
        label = sample['label']
    
        # 1. Ensure RGB
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Perform resize if dimensions changed
        image = image.resize(SIZE)
            
        # Convert to numpy uint8 immediately to save RAM (PIL objects are heavy)
        img_arr = np.array(image, dtype=np.uint8)
        
        images.append(img_arr)
        labels.append(label)
        
        # 4. Check Capacity
        if len(images) >= SLICE_SIZE:
            flush_buffer(images, labels, slice_count)
            images = []
            labels = []
            slice_count += 1
    
    # --- FINAL CLEANUP ---
    print("Flushing remaining buffers...")
    flush_buffer(images, labels, slice_count)
    
    print("Done.")
    
if __name__ == "__main__":
    main()