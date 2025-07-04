import os
import numpy as np
import torch
from torch.utils.data import Dataset
from utils import events_to_voxel_grid, get_closest_range

class EventVelocityDataset(Dataset):
    def __init__(self, folder_path, shape=(200, 200), bins=5, window_size=200, device='cpu'):
    
        self.shape = shape
        self.bins = bins
        self.window_size = window_size  # 200 events before/after
        self.samples = []
        self.device = device
        self.sequences = []

        npz_files = sorted([f for f in os.listdir(folder_path)])

        for file_idx, file_name in enumerate(npz_files):
            path = os.path.join(folder_path, file_name)
            data = np.load(path)

            events_np = np.stack([
                data["events"]['x'],
                data["events"]['y'],
                data["events"]['p'].astype(np.int8),
                data["events"]['t'].astype(np.float32),
            ], axis=-1)

            events = torch.from_numpy(events_np).to(torch.float32)
            timestamps = torch.from_numpy(data["timestamps"]).to(torch.float32)
            traj = torch.from_numpy(data["traj"]).to(torch.float32)
            range_meter = torch.from_numpy(data["range_meter"]).to(torch.float32)

            ts_us = timestamps * 1e6
            event_times = events[:, 3]

            self.sequences.append({
                "events": events,
                "event_times": event_times,
                "traj": traj,
                "timestamps": timestamps,
                "ts_us": ts_us,
                "range_meter": range_meter,
            })

            for ts_idx in range(len(ts_us)):
                for bin_idx in range(bins):
                    self.samples.append((file_idx, ts_idx, bin_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):


        seq_idx, ts_idx, bin_idx = self.samples[index]

        
        seq = self.sequences[seq_idx]

        t_center = seq["ts_us"][ts_idx]

        t_start = t_center - self.window_size * 1000
        t_end = t_center + self.window_size * 1000

        mask = (seq["event_times"] >= t_start) & (seq["event_times"] <= t_end)
        events_slice = seq["events"][mask]

        if len(events_slice) == 0:
            voxel = torch.zeros((self.bins, *self.shape), dtype=torch.float32, device=self.device)
        else:
            voxel = events_to_voxel_grid(events_slice.to(self.device), shape=self.shape, bins=self.bins, device=self.device)

        bin_image = voxel[bin_idx]
        velocity = seq["traj"][ts_idx, 3:6].to(self.device)
        ts = seq["timestamps"][ts_idx]
        range_val = get_closest_range(seq["range_meter"], ts)

        return bin_image.unsqueeze(0), range_val, velocity