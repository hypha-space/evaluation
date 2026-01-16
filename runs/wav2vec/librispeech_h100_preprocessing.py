import torch
import datasets
import numpy as np
from transformers import Wav2Vec2Model, AutoFeatureExtractor, AutoConfig, Wav2Vec2ForPreTraining, Wav2Vec2Processor, Wav2Vec2ForCTC
from safetensors.torch import save
import os
import snappy

def snappy_safetensor(tensor_dict, file_path:str):
    # I/O Compression
    tensor_data = save(tensor_dict)
    with open(file_path, 'wb') as out_file:
        out_file.write(snappy.compress(tensor_data))


def estimate_cutoffs():
    ds = datasets.load_dataset("openslr/librispeech_asr", "clean", split="test", streaming=True)
    ds = ds.remove_columns(["file", "speaker_id", "chapter_id", "id"])
    audio_legnths = []

    for i, sample in tqdm(enumerate(ds), total=28539): # Total count for ImageNet Train
        audio_legnths.append(sample["audio"]["array"].shape[0])

    filtered = np.array([i for i in audio_legnths if 4000 < i < 320000])
    val, counts = np.unique(np.ceil(filtered / 128), return_counts=True)
    bin_cut_offs = np.array([ int(np.argmin(counts.cumsum() < counts.sum() / 10 * i)) for i in range(1,11)]) * 128


def main():
    processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base", fast=True)
    
    ds = datasets.load_dataset("openslr/librispeech_asr", "clean", split="test", streaming=True)
    ds = ds.remove_columns(["file", "speaker_id", "chapter_id", "id"])
    
    data_path = "data/librispeech_100_test/"
    bin_cut_offs = np.array([ 72320, 134528, 166528, 181888, 192128, 200448, 207360, 214144, 221184, 243968, 320000])
    buffer = [[] for i in range(11)]
    counter = [0 for i in range(11)]
    samples_per_file = 100
    for i, sample in tqdm(enumerate(ds), total=28539): # Total count for 100h Train
        audio_array = sample["audio"]["array"]
        if 4000 < audio_array.shape[0] < 320000:
            bin_idx = np.argmax(audio_array.shape[0] <= bin_cut_offs) 
            
            input_len = audio_array.shape[0] // 320
            label_len = len(processor.tokenizer(sample["text"], add_special_tokens=False)["input_ids"])
            if input_len < label_len + 2:
                print(f"Skipped impossible alignment: {input_len} frames vs {label_len} tokens")
                continue
        
            processed_inputs = processor(
                audio=audio_array, 
                padding='max_length',
                max_length=bin_cut_offs[bin_idx],
                sampling_rate=16000, 
                truncation=True,
                return_attention_mask=True,
                return_tensors="pt"
            )
        
            # Store input_values AND the audio attention_mask
            buffer[bin_idx].append({
                "input_values": processed_inputs.input_values, 
                "attention_mask": processed_inputs.attention_mask, # Save Audio Mask
                "text": sample["text"]
            })
        
            if len(buffer[bin_idx]) == samples_per_file:
                # Tokenize the text labels
                tokenized = processor.tokenizer(
                    [b["text"] for b in buffer[bin_idx]],
                    padding="longest",
                    return_tensors="pt"
                )
                
                labels = tokenized.input_ids
                # Replace the pad_token_id (usually 0) with -100 so CTC loss ignores them
                labels[labels == processor.tokenizer.pad_token_id] = -100
                
                snappy_safetensor(
                    {
                        # Concat the audio inputs
                        "input_values": torch.concat([b["input_values"] for b in buffer[bin_idx]]),
                        
                        # Concat the AUDIO attention masks (Not the text ones!)
                        "attention_mask": torch.concat([b["attention_mask"] for b in buffer[bin_idx]]),
                        
                        # Use the masked labels
                        "labels": labels
                    }
                    f"{data_path}train_{bin_cut_offs[bin_idx]}_{counter[bin_idx]}.saftensor.snappy"
                )
                buffer[bin_idx] = []
                counter[bin_idx] += 1
                break

if __name__ == "__main__":
    main()