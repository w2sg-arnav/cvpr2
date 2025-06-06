# Enhanced augmentations specifically for cotton leaf disease classification
# phase4_finetuning/utils/augmentations.py
from typing import Tuple, Optional, Dict, Any, List
import torch
import torchvision.transforms.v2 as T_v2
import torchvision.transforms.functional as TF
import logging
import numpy as np
import random
from typing import Tuple, List

logger = logging.getLogger(__name__)

class CottonLeafDiseaseAugmentation:
    """
    Specialized augmentations for cotton leaf disease classification.
    Designed to simulate realistic variations in agricultural imaging conditions.
    """
    def __init__(self, img_size: tuple, severity: str = 'moderate',
                 use_mixup: bool = True, use_cutmix: bool = True): # These mixup flags are for internal use if any.
        self.img_size = img_size
        self.severity = severity
        # These flags are if this class itself were to apply mixup/cutmix.
        # In the current setup, EnhancedFinetuner handles mixup/cutmix globally.
        # So, these will likely be passed as False from the factory.
        self.internal_use_mixup = use_mixup
        self.internal_use_cutmix = use_cutmix

        severity_configs = {
            'mild': {
                'rotation_degrees': 15,
                'color_jitter_params': (0.2, 0.2, 0.2, 0.1),
                'translate': (0.1, 0.1),
                'scale': (0.8, 1.2),
                'shear': 8,
                'perspective_prob': 0.3,
                'perspective_scale': 0.2,
                'blur_prob': 0.2,
                'blur_kernel': (3, 7),
                'blur_sigma': (0.1, 1.2),
                'erase_prob': 0.1,
                'erase_scale': (0.02, 0.08),
                'lighting_prob': 0.4,
                'shadow_prob': 0.3,
                'noise_prob': 0.2
            },
            'moderate': {
                'rotation_degrees': 25,
                'color_jitter_params': (0.3, 0.3, 0.25, 0.15),
                'translate': (0.15, 0.15),
                'scale': (0.7, 1.3),
                'shear': 12,
                'perspective_prob': 0.4,
                'perspective_scale': 0.25,
                'blur_prob': 0.25,
                'blur_kernel': (3, 9),
                'blur_sigma': (0.1, 1.5),
                'erase_prob': 0.15,
                'erase_scale': (0.02, 0.12),
                'lighting_prob': 0.5,
                'shadow_prob': 0.4,
                'noise_prob': 0.3
            },
            'strong': { # Corresponds to "high" severity in config
                'rotation_degrees': 35,
                'color_jitter_params': (0.4, 0.4, 0.3, 0.2),
                'translate': (0.2, 0.2),
                'scale': (0.6, 1.4),
                'shear': 15,
                'perspective_prob': 0.5,
                'perspective_scale': 0.3,
                'blur_prob': 0.3,
                'blur_kernel': (3, 11),
                'blur_sigma': (0.1, 2.0),
                'erase_prob': 0.2,
                'erase_scale': (0.02, 0.15),
                'lighting_prob': 0.6,
                'shadow_prob': 0.5,
                'noise_prob': 0.4
            },
             'high': { # Explicitly add 'high' if config uses it
                'rotation_degrees': 35,
                'color_jitter_params': (0.4, 0.4, 0.3, 0.2),
                'translate': (0.2, 0.2),
                'scale': (0.6, 1.4),
                'shear': 15,
                'perspective_prob': 0.5,
                'perspective_scale': 0.3,
                'blur_prob': 0.3,
                'blur_kernel': (3, 11),
                'blur_sigma': (0.1, 2.0),
                'erase_prob': 0.2,
                'erase_scale': (0.02, 0.15),
                'lighting_prob': 0.6,
                'shadow_prob': 0.5,
                'noise_prob': 0.4
            }
        }

        config_params = severity_configs.get(severity, severity_configs['moderate'])
        logger.info(f"CottonLeafDiseaseAugmentation using severity '{severity}' with params: {config_params}")

        transforms_list = [
            T_v2.RandomResizedCrop(size=self.img_size, scale=config_params['scale'], ratio=(0.75, 1.33), interpolation=T_v2.InterpolationMode.BILINEAR, antialias=True), # Added RRC
            T_v2.RandomHorizontalFlip(p=0.5),
            T_v2.RandomVerticalFlip(p=0.5),
            T_v2.RandomRotation(degrees=config_params['rotation_degrees'], interpolation=T_v2.InterpolationMode.BILINEAR, fill=0.0), # fill can be a tuple for 3 channels
            T_v2.RandomAffine(degrees=config_params['rotation_degrees'] // 2, translate=config_params['translate'], scale=config_params['scale'], shear=config_params['shear'], interpolation=T_v2.InterpolationMode.BILINEAR, fill=0.0),
            T_v2.RandomPerspective(distortion_scale=config_params['perspective_scale'], p=config_params['perspective_prob'], interpolation=T_v2.InterpolationMode.BILINEAR, fill=0.0),
            EnhancedColorJitter(brightness=config_params['color_jitter_params'][0], contrast=config_params['color_jitter_params'][1], saturation=config_params['color_jitter_params'][2], hue=config_params['color_jitter_params'][3]),
            T_v2.RandomApply([LightingVariation()], p=config_params['lighting_prob']),
            T_v2.RandomApply([SyntheticShadow()], p=config_params['shadow_prob']),
            T_v2.RandomApply([T_v2.GaussianBlur(kernel_size=self._ensure_odd_tuple(config_params['blur_kernel']), sigma=config_params['blur_sigma'])], p=config_params['blur_prob']),
            T_v2.RandomApply([GaussianNoise(std=0.02)], p=config_params['noise_prob']), # Assuming images are [0,1] before this
            StableRandomErasing(p=config_params['erase_prob'], scale=config_params['erase_scale'], ratio=(0.3, 3.0)),
            T_v2.ToDtype(torch.float32, scale=True), # Convert to float and scale if input is uint8
            T_v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) # Normalize at the end
        ]

        self.transform_pipeline = T_v2.Compose(transforms_list)

        # MixUp and CutMix parameters (for internal use, if this class were to apply them)
        self.mixup_alpha = 0.2
        self.cutmix_alpha = 1.0
        self.mix_prob = 0.3 # Probability of this class applying mixing if internal_use_mixup/cutmix is True

    def _ensure_odd_tuple(self, val):
        if isinstance(val, int): return (val if val % 2 != 0 else val + 1,) * 2
        if isinstance(val, (list, tuple)): return tuple(v if v % 2 != 0 else v + 1 for v in val)
        return (3, 3) # Default kernel size

    def __call__(self, x_batch: torch.Tensor, targets: Optional[torch.Tensor] = None) -> tuple:
        # The input x_batch from SARCLD2024Dataset is expected to be a PIL Image or a batch of PIL Images.
        # If it's a batch, transforms need to be applied per image or the batch needs to be a tensor.
        # Assuming x_batch is a single PIL Image from dataset __getitem__
        # The ToDtype and Normalize are now part of the pipeline.

        augmented_x = self.transform_pipeline(x_batch)

        # Internal mixup/cutmix logic (likely unused if EnhancedFinetuner handles it)
        if targets is not None and self.mix_prob > 0 and (self.internal_use_mixup or self.internal_use_cutmix):
            # This block would only execute if internal_use_mixup/cutmix were True
            # AND this class was directly responsible for it.
            # In the current setup, EnhancedFinetuner in main.py handles these.
            if random.random() < 0.5 and self.internal_use_mixup and self.mixup_alpha > 0:
                # This assumes augmented_x is now a batch tensor if targets is a batch.
                # This internal mixup is problematic if __call__ receives a single image.
                # For now, this internal logic is dormant due to how it's called.
                logger.debug("Internal Mixup applied by CottonLeafDiseaseAugmentation (should be rare)")
                augmented_x, targets = self._mixup(augmented_x, targets)
            elif self.internal_use_cutmix and self.cutmix_alpha > 0:
                logger.debug("Internal CutMix applied by CottonLeafDiseaseAugmentation (should be rare)")
                augmented_x, targets = self._cutmix(augmented_x, targets)

        # Stability check already handled by Normalize if inputs are bounded,
        # but an explicit clamp after all ops can be a safeguard if intermediate ops might go wild.
        # augmented_x = torch.clamp(augmented_x, min=-3.5, max=3.5) # Clamping normalized data is tricky

        if not torch.isfinite(augmented_x).all():
            logger.warning("Non-finite values detected in augmented image. Returning original (if possible, else error).")
            # Fallback to a minimally processed original image might be complex here if x_batch was PIL
            # Simplest is to let it error or return a black image of correct size
            return torch.zeros_like(augmented_x), targets if targets is not None else torch.zeros_like(augmented_x)


        if targets is not None:
            return augmented_x, targets
        return augmented_x # If called without targets (e.g. for visualization)

    def _mixup(self, x: torch.Tensor, y: torch.Tensor) -> tuple:
        batch_size = x.size(0)
        lam = np.random.beta(self.mixup_alpha, self.mixup_alpha)
        index = torch.randperm(batch_size).to(x.device)
        mixed_x = lam * x + (1 - lam) * x[index, :]
        y_a, y_b = y, y[index]
        return mixed_x, (y_a, y_b, lam) # Target format for mixed loss

    def _cutmix(self, x: torch.Tensor, y: torch.Tensor) -> tuple:
        batch_size = x.size(0)
        lam = np.random.beta(self.cutmix_alpha, self.cutmix_alpha)
        index = torch.randperm(batch_size).to(x.device)
        bbx1, bby1, bbx2, bby2 = self._rand_bbox(x.size(), lam)
        # Ensure x is writable; clone if it's a view or has other issues
        x_cloned = x.clone()
        x_cloned[:, :, bby1:bby2, bbx1:bbx2] = x[index, :, bby1:bby2, bbx1:bbx2]
        lam = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (x.size()[-1] * x.size()[-2]))
        y_a, y_b = y, y[index]
        return x_cloned, (y_a, y_b, lam)

    def _rand_bbox(self, size, lam):
        W, H = size[2], size[3]
        cut_rat = np.sqrt(1. - lam)
        cut_w, cut_h = int(W * cut_rat), int(H * cut_rat)
        cx, cy = np.random.randint(W), np.random.randint(H)
        bbx1, bby1 = np.clip(cx - cut_w // 2, 0, W), np.clip(cy - cut_h // 2, 0, H)
        bbx2, bby2 = np.clip(cx + cut_w // 2, 0, W), np.clip(cy + cut_h // 2, 0, H)
        return bbx1, bby1, bbx2, bby2

class EnhancedColorJitter(torch.nn.Module):
    def __init__(self, brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1):
        super().__init__()
        self.base_jitter = T_v2.ColorJitter(brightness=brightness, contrast=contrast, saturation=saturation, hue=hue)
        self.chlorosis_prob = 0.2
        self.necrosis_prob = 0.15

    def forward(self, img_batch: torch.Tensor) -> torch.Tensor:
        # img_batch is expected to be a tensor, possibly already normalized if not called first.
        # For HSV conversion, it's better to work with [0,1] unnormalized images.
        # This class is now part of a pipeline that normalizes at the end.

        is_batch = img_batch.ndim == 4
        if not is_batch: img_batch = img_batch.unsqueeze(0)

        # Apply base ColorJitter
        if random.random() < 0.8: # Apply base jitter with high probability
             img_batch = self.base_jitter(img_batch)

        # Disease-specific color variations (applied per image in batch)
        for i in range(img_batch.shape[0]):
            img = img_batch[i] # C, H, W
            if random.random() < self.chlorosis_prob:
                img = self._simulate_chlorosis(img)
            if random.random() < self.necrosis_prob:
                img = self._simulate_necrosis(img)
            img_batch[i] = img

        return img_batch if is_batch else img_batch.squeeze(0)

    def _simulate_chlorosis(self, img: torch.Tensor) -> torch.Tensor: # img is C, H, W tensor [0,1]
        # Convert to HSV, apply changes, convert back.
        # torchvision.transforms.functional.rgb_to_hsv and hsv_to_rgb expect (..., 3, H, W)
        img_hsv = TF.rgb_to_hsv(img) # (3, H, W)
        # H component is [0,1] representing [0, 360 degrees]
        # S, V are [0,1]
        # Yellow is around H = 60/360 = 0.167. Green around 120/360 = 0.333
        # Shift hue slightly towards yellow: decrease H if green, increase if blueish-green
        # This is tricky. A simpler approach might be to directly manipulate RGB channels for yellowing:
        # Increase Red and Green, slightly decrease Blue.
        # For chlorosis (yellowing): less green, more yellow-ish
        # Example: increase R, keep G high, decrease B, desaturate a bit.
        # This requires careful tuning. A simpler heuristic:
        r, g, b = img[0], img[1], img[2]
        new_g = g * random.uniform(0.7, 0.9) # Reduce green
        new_r = r * random.uniform(1.0, 1.1) + (g - new_g) * 0.5 # Compensate with red
        img_mod = torch.stack([torch.clamp(new_r,0,1), torch.clamp(new_g,0,1), b * random.uniform(0.8,1.0)], dim=0)
        return img_mod

    def _simulate_necrosis(self, img: torch.Tensor) -> torch.Tensor: # img is C, H, W tensor [0,1]
        # Browning: reduce saturation and shift hue towards orange/brown.
        # Simple RGB manipulation: More R, less G and B, desaturate.
        brown_factor = random.uniform(0.1, 0.3)
        desat_factor = random.uniform(0.6, 0.9)
        gray = TF.rgb_to_grayscale(img.unsqueeze(0), num_output_channels=3).squeeze(0) # (3,H,W)
        # Blend towards a brownish color (e.g. more red, less blue)
        # A simple browning could be:
        r, g, b = img[0], img[1], img[2]
        # Shift towards brown: R up, G slightly down, B down
        new_r = torch.clamp(r * (1 + brown_factor * 0.5) + g * brown_factor * 0.2, 0, 1)
        new_g = torch.clamp(g * (1 - brown_factor * 0.3), 0, 1)
        new_b = torch.clamp(b * (1 - brown_factor * 0.6), 0, 1)
        img_mod = torch.stack([new_r, new_g, new_b], dim=0)
        # Desaturate
        img_mod = img_mod * desat_factor + gray * (1-desat_factor)
        return torch.clamp(img_mod, 0, 1)


class LightingVariation(torch.nn.Module):
    def __init__(self): super().__init__()
    def forward(self, img: torch.Tensor) -> torch.Tensor: # Assumes img is [0,1] tensor
        variation_type = random.choice(['overexposure', 'underexposure', 'uneven_h', 'uneven_v'])
        if variation_type == 'overexposure': factor = random.uniform(1.1, 1.4); img_mod = torch.clamp(img * factor, 0, 1)
        elif variation_type == 'underexposure': factor = random.uniform(0.6, 0.9); img_mod = img * factor
        else: # uneven
            h, w = img.shape[-2:]
            if variation_type == 'uneven_h': # Horizontal gradient
                gradient = torch.linspace(random.uniform(0.7,0.9), random.uniform(1.1,1.3), w, device=img.device).view(1, 1, -1)
            else: # Vertical gradient
                gradient = torch.linspace(random.uniform(0.7,0.9), random.uniform(1.1,1.3), h, device=img.device).view(1, -1, 1)
            img_mod = torch.clamp(img * gradient, 0, 1)
        return img_mod

class SyntheticShadow(torch.nn.Module):
    def __init__(self): super().__init__()
    def forward(self, img_batch: torch.Tensor) -> torch.Tensor: # Assumes img_batch is B,C,H,W [0,1]
        is_batch = img_batch.ndim == 4
        if not is_batch: img_batch = img_batch.unsqueeze(0)

        for i in range(img_batch.shape[0]):
            img = img_batch[i] # C,H,W
            c, h, w = img.shape
            shadow_type = random.choice(['ellipse', 'rectangle', 'irregular'])
            if shadow_type == 'ellipse': mask = self._create_ellipse_mask(h, w, device=img.device)
            elif shadow_type == 'rectangle': mask = self._create_rectangle_mask(h, w, device=img.device)
            else: mask = self._create_irregular_mask(h, w, device=img.device)
            shadow_intensity = random.uniform(0.3, 0.7)
            # Mask should be (H,W), expand to (C,H,W) for broadcasting
            img_batch[i] = img * (1 - mask.unsqueeze(0) * shadow_intensity)
        return img_batch if is_batch else img_batch.squeeze(0)

    def _create_ellipse_mask(self, h: int, w: int, device) -> torch.Tensor:
        mask = torch.zeros(h, w, device=device)
        cx, cy = random.randint(w//4, 3*w//4), random.randint(h//4, 3*h//4)
        a, b = random.randint(w//8, w//3), random.randint(h//8, h//3)
        y, x = torch.meshgrid(torch.arange(h, device=device), torch.arange(w, device=device), indexing='ij')
        ellipse = ((x - cx) / (a + 1e-6)) ** 2 + ((y - cy) / (b + 1e-6)) ** 2
        mask[ellipse <= 1] = 1
        return mask
    def _create_rectangle_mask(self, h: int, w: int, device) -> torch.Tensor:
        mask = torch.zeros(h, w, device=device)
        x1, y1 = random.randint(0, w//2), random.randint(0, h//2)
        x2, y2 = random.randint(w//2, w-1), random.randint(h//2, h-1) # ensure x2/y2 > x1/y1
        mask[min(y1,y2):max(y1,y2)+1, min(x1,x2):max(x1,x2)+1] = 1
        return mask
    def _create_irregular_mask(self, h: int, w: int, device) -> torch.Tensor:
        mask = torch.zeros(h, w, device=device)
        for _ in range(random.randint(2, 5)):
            cx, cy = random.randint(0, w), random.randint(0, h)
            radius = random.randint(min(h, w)//10, min(h, w)//3)
            y, x = torch.meshgrid(torch.arange(h, device=device), torch.arange(w, device=device), indexing='ij')
            circle = (x - cx) ** 2 + (y - cy) ** 2
            mask[circle <= radius ** 2] = 1
        return mask

class GaussianNoise(torch.nn.Module):
    def __init__(self, std=0.02): super().__init__(); self.std = std
    def forward(self, img: torch.Tensor) -> torch.Tensor: # Assumes img is [0,1]
        noise = torch.randn_like(img) * self.std
        return torch.clamp(img + noise, 0, 1)

class StableRandomErasing(torch.nn.Module):
    def __init__(self, p=0.1, scale=(0.02, 0.12), ratio=(0.3, 3.0)):
        super().__init__()
        self.eraser = T_v2.RandomErasing(p=p, scale=scale, ratio=ratio, value=0.0, inplace=False)
    def forward(self, img: torch.Tensor) -> torch.Tensor: return self.eraser(img)


def create_cotton_leaf_augmentation(
    strategy: str = 'cotton_disease',
    img_size: tuple = (448, 448),
    **kwargs
):
    logger.info(f"Creating augmentation strategy: '{strategy}' for image size {img_size}")

    # Map "aggressive_medical" from config to a severity level
    # The config uses "augmentation_severity": "high"
    if strategy == 'aggressive_medical':
        severity_map = {'mild': 'mild', 'moderate': 'moderate', 'high': 'strong'}
        # Get severity from kwargs (passed from main.py based on config) or default.
        config_severity = kwargs.get('severity', 'high') # 'high' from config
        mapped_severity = severity_map.get(config_severity, 'strong') # Map 'high' to 'strong'
        logger.info(f"Strategy '{strategy}' using CottonLeafDiseaseAugmentation with severity '{mapped_severity}'")
        return CottonLeafDiseaseAugmentation(
            img_size,
            severity=mapped_severity,
            use_mixup=False, # Trainer will handle mixup/cutmix
            use_cutmix=False
        )
    elif strategy == 'cotton_disease': # Direct call with this strategy name
        severity = kwargs.get('severity', 'moderate')
        return CottonLeafDiseaseAugmentation(
            img_size,
            severity=severity,
            use_mixup=False,
            use_cutmix=False
        )
    else:
        logger.warning(f"Strategy '{strategy}' not explicitly handled by create_cotton_leaf_augmentation. "
                       f"Returning a minimal T_v2 transform (Resize, ToDtype, Normalize). "
                       f"Ensure this is intended or add handling for '{strategy}'.")
        # Fallback to a very basic set of transforms if strategy is unknown to this factory.
        # Normalization is crucial.
        return T_v2.Compose([
            T_v2.Resize(img_size, interpolation=T_v2.InterpolationMode.BILINEAR, antialias=True),
            T_v2.ToDtype(torch.float32, scale=True), # Assumes input images are uint8
            T_v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])