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
    data_dir = "data/imagenet_streaming_train"
    os.makedirs(data_dir, exist_ok=True)
    
    # Format: (Width, Height) because PIL uses (W, H)
    MAX_SIZE = (256, 480) 
    SLICE_SIZE = 1000
    
    # State Management
    # buffers = { (w, h): {'images': [img1, ...], 'labels': [0, ...]} }
    buffers = {}
    # slice_counts = { (w, h): current_file_index }
    slice_counts = {}
    
    # --- HELPER: FLUSH TO DISK ---
    def flush_buffer(w, h):
        """Writes the current buffer for resolution (w,h) to disk and clears it."""
        imgs = buffers[(w, h)]['images']
        lbls = buffers[(w, h)]['labels']
        
        if not imgs:
            return
    
        # 1. Stack and Convert
        # List of (H, W, 3) -> Tensor (N, 3, H, W)
        # converting to uint8 saves massive space/time
        batch_tensor = torch.from_numpy(np.stack(imgs)).permute(0, 3, 1, 2).contiguous()
        label_tensor = torch.tensor(lbls, dtype=torch.int64)
        
        # 2. Determine Filename
        # User requested: train_{h}_{w}_{slice_count}
        idx = slice_counts.get((w, h), 0)
        filename = os.path.join(data_dir, f"train_{h}_{w}_{idx}_safetensor.snappy")
        
        # 3. Save
        # If you need snappy output, use this instead:
        with open(filename, "wb") as f:
            f.write(compress(save({"images": batch_tensor, "labels": label_tensor})))
        
        # 4. Reset
        buffers[(w, h)]['images'] = []
        buffers[(w, h)]['labels'] = []
        slice_counts[(w, h)] = idx + 1
        
        # Optional: Print only every few saves to avoid clutter
        # print(f"Saved {filename} ({len(imgs)} items)")
    
    # --- MAIN LOOP ---
    # streaming=True ensures we process one sample at a time without loading everything
    print("Loading streaming dataset...")
    ds = datasets.load_dataset("ILSVRC/imagenet-1k", split="train", streaming=True)
    
    print("Starting iteration...")
    for i, sample in tqdm(enumerate(ds), total=1281167): # Total count for ImageNet Train
        image = sample['image']
        label = sample['label']
    
        # 1. Ensure RGB
        if image.mode != "RGB":
            image = image.convert("RGB")
    
        # 2. Resize Logic
        # PIL size is (Width, Height)
        w_curr, h_curr = image.size

        if w_curr < 224 or h_curr < 244:
            continue
        
        # Clamp dimensions to MAX_SIZE
        target_w = min(w_curr, MAX_SIZE[0])
        target_h = min(h_curr, MAX_SIZE[1])
        
        # Perform resize if dimensions changed
        if (target_w, target_h) != (w_curr, h_curr):
            image = image.resize((target_w, target_h))
        
        # 3. Buffer Management
        key = (target_w, target_h)
        
        if key not in buffers:
            buffers[key] = {'images': [], 'labels': []}
            
        # Convert to numpy uint8 immediately to save RAM (PIL objects are heavy)
        img_arr = np.array(image, dtype=np.uint8)
        
        buffers[key]['images'].append(img_arr)
        buffers[key]['labels'].append(label)
        
        # 4. Check Capacity
        if len(buffers[key]['images']) >= SLICE_SIZE:
            flush_buffer(target_w, target_h)
    
    # --- FINAL CLEANUP ---
    print("Flushing remaining buffers...")
    # Iterate over a copy of keys because we might modify buffers (though flush doesn't delete keys)
    for (w, h) in list(buffers.keys()):
        flush_buffer(w, h)
    
    print("Done.")
    
if __name__ == "__main__":
    main()