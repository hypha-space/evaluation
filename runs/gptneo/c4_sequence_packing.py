from safetensors.torch import save

data_path = "data/c4_en/train"
BLOCK_SIZE=512
SLICE_SIZE=5000

import torch
import torch.nn.functional as F
from safetensors.torch import save, load
import os
import snappy

def snappy_safetensor(tensor_dict, file_path:str):
    # I/O Compression
    tensor_data = save(tensor_dict)
    with open(file_path, 'wb') as out_file:
        out_file.write(snappy.compress(tensor_data))

def read_snappy_safetensor(file_path: str):
    with open(file_path, "rb") as file:
        raw_bytes = snappy.uncompress(file.read())
    return load(raw_bytes)


def map_to_batch(batch, idx):
    # 1. Fast Tokenization
    # We strip 'attention_mask' here immediately
    raw_tokenized = tokenizer(
        batch["text"],
        add_special_tokens=True, # Adds BOS (if model has one)
        return_attention_mask=False 
    )["input_ids"]

    split_value = tokenizer.encode(["."])[0]
    tokenized = []
    lengths = []
    for t in raw_tokenized:
        if len(t) <= BLOCK_SIZE - 1:
            tokenized.append(t + [tokenizer.eos_token_id])
            lengths.append(len(t) + 1)
        else:
            # split by . = 13
            while len(t) > BLOCK_SIZE-1:
                dot_pos = np.argwhere(np.array(t) == split_value)
                if dot_pos.size == 0:
                    break
                split_pos = np.max((dot_pos < (BLOCK_SIZE - 1)) * dot_pos)
                tokenized.append(t[:split_pos] + [tokenizer.eos_token_id])
                lengths.append(split_pos + 1)
                t = t[split_pos+1:]
    
    # Sort for optimal packing (First Fit Decreasing)
    indexed_lengths = sorted(
        [(l, i) for i, l in enumerate(lengths)], 
        key=lambda x: x[0], 
        reverse=True
    )

    bins = []
    bin_space = [] 

    # Packing Logic
    for length, index in indexed_lengths:
        placed = False
        for i in range(len(bins)):
            # O(1) capacity check
            if bin_space[i] >= length:
                bins[i].append((length, index))
                bin_space[i] -= length
                placed = True
                break
        
        if not placed:
            bins.append([(length, index)])
            bin_space.append(BLOCK_SIZE - length)

    # 3. Vectorized Tensor Construction
    out_input_ids = []
    out_position_ids = []
    slice_counter = 0

    for _bin in bins:
        combined_ids = []
        combined_pos = []

        for length, original_idx in _bin:
            # Fetch tokens
            seq = tokenized[original_idx]
            combined_ids.extend(seq)
            
            # --- CRITICAL: Reset Position IDs ---
            # Instead of a mask, we simply tell the model "we are back at index 0"
            # distinct sequences: [0, 1, 2] ... [0, 1, 2, 3]
            combined_pos.extend(list(range(length)))

        # Convert to Tensor (uint16 is enough for vocab < 65k, else use int32)
        # Position IDs usually fit in uint16 (0-1024)
        ids_tensor = torch.tensor(combined_ids, dtype=torch.int32) 
        pos_tensor = torch.tensor(combined_pos, dtype=torch.int16)

        # 4. Fast Padding (F.pad)
        # Pad both Input IDs and Position IDs to fill the 1024 block
        pad_len = BLOCK_SIZE - ids_tensor.shape[0]
        
        if pad_len > 0:
            # Pad inputs with EOS (or PAD)
            ids_tensor = F.pad(ids_tensor, (0, pad_len), value=tokenizer.eos_token_id)
            # Pad positions with 0 (ignored by model usually, or continue counter)
            pos_tensor = F.pad(pos_tensor, (0, pad_len), value=0)
            
        out_input_ids.append(ids_tensor)
        out_position_ids.append(pos_tensor)

        if len(out_input_ids) == SLICE_SIZE:
            file_path = f"{data_path}/train_{idx[0]}_{slice_counter}_safetensor.snappy"
            # 5. Stack & Save
            # We drop 'attention_mask' entirely
            tensor_dict = {
                "input_ids": torch.stack(out_input_ids), 
                "position_ids": torch.stack(out_position_ids)
            }
    
            snappy_safetensor(tensor_dict, file_path)
            out_input_ids = []
            out_position_ids = []
            slice_counter += 1

    if len(out_input_ids) > 0:
        file_path = f"{data_path}/train_{idx[0]}_rest_safetensor.snappy"
        # 5. Stack & Save
        # We drop 'attention_mask' entirely
        tensor_dict = {
            "input_ids": torch.stack(out_input_ids), 
            "position_ids": torch.stack(out_position_ids)
        }
        snappy_safetensor(tensor_dict, file_path)

def process_rest(all_files):
    # Buffers to store tensors temporarily (list of tensors is O(1) to append)
    input_buffer = []
    pos_buffer = []
    buffer_length = 0
    counter = 0
    
    # Loop through files
    while len(all_files) > 0:
        print(f"Files {len(all_files)} left")
        file = all_files.pop()
        
        # 1. Read data
        tensor_dict = read_snappy_safetensor(file)
        
        # 2. Append to list (Zero-copy operation)
        new_input = tensor_dict["input_ids"]
        new_pos = tensor_dict["position_ids"]
        
        input_buffer.append(new_input)
        pos_buffer.append(new_pos)
        buffer_length += new_input.shape[0]
    
        # 3. Process only when we have enough data for at least one slice
        while buffer_length >= SLICE_SIZE:
            # Concatenate everything currently in the buffer
            # This is the ONLY time we allocate heavy memory
            full_input = torch.cat(input_buffer, dim=0)
            full_pos = torch.cat(pos_buffer, dim=0)
            
            # 4. Extract the exact slice we need
            save_input = full_input[:SLICE_SIZE]
            save_pos = full_pos[:SLICE_SIZE]
            
            # 5. Save the slice
            file_path = f"{data_path}/train_{counter}_safetensor.snappy"
            out_dict = {
                "input_ids": save_input,
                "position_ids": save_pos
            }
            snappy_safetensor(out_dict, file_path)
            counter += 1
            
            # 6. Handle the remainder
            # We keep ONLY the leftover data in the buffer
            remainder_input = full_input[SLICE_SIZE:]
            remainder_pos = full_pos[SLICE_SIZE:]
            
            # Reset buffers with just the remainder
            input_buffer = [remainder_input]
            pos_buffer = [remainder_pos]
            buffer_length = remainder_input.shape[0]
        os.remove(file)

if __name__ == "__main__":
    ds = datasets.load_dataset("allenai/c4", "en", split="train", token="...")
    tokenizer = GPT2Tokenizer.from_pretrained("EleutherAI/gpt-neo-1.3B", use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token
    ds.map(map_to_batch, batched=True, batch_size=int(SLICE_SIZE * 1.75), with_indices=True, num_proc=50) 
    process_rest([f"{data_path}/{f}" for f in os.listdir(data_path) if "rest" in f])