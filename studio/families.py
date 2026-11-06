"""The 'Simple' view: which options matter most, and sensible starting values per model family.

Only options the chosen script actually accepts are shown, so this list can be generous.
"""

SIMPLE_SECTIONS = [
    ("Model", [
        "pretrained_model_name_or_path", "vae", "ae", "clip_l", "clip_g", "t5xxl", "qwen3",
        "gemma2", "text_encoder", "network_weights", "resume",
    ]),
    ("Output", [
        "output_dir", "output_name", "save_model_as", "save_precision", "save_every_n_epochs",
        "save_last_n_epochs", "save_state", "logging_dir",
    ]),
    ("Network", [
        "network_module", "network_dim", "network_alpha", "network_args", "network_train_unet_only",
        "network_train_text_encoder_only", "network_dropout",
    ]),
    ("Learning", [
        "optimizer_type", "learning_rate", "unet_lr", "text_encoder_lr", "optimizer_args",
        "lr_scheduler", "lr_warmup_steps", "lr_scheduler_num_cycles", "max_grad_norm",
    ]),
    ("Length", [
        "max_train_epochs", "max_train_steps", "gradient_accumulation_steps", "seed",
    ]),
    ("Memory & speed", [
        "mixed_precision", "gradient_checkpointing", "cache_latents", "cache_latents_to_disk",
        "cache_text_encoder_outputs", "cache_text_encoder_outputs_to_disk", "fp8_base",
        "blocks_to_swap", "unsloth_offload_checkpointing", "sdpa", "xformers",
        "max_data_loader_n_workers", "persistent_data_loader_workers",
    ]),
    ("Noise & timesteps", [
        "timestep_sampling", "discrete_flow_shift", "sigmoid_scale", "model_prediction_type",
        "guidance_scale", "weighting_scheme", "min_snr_gamma", "noise_offset", "loss_type",
        "huber_schedule", "huber_c", "huber_scale",
    ]),
]

COMMON_DEFAULTS = {
    "output_name": "my_lora",
    "save_model_as": "safetensors",
    "save_precision": "bf16",
    "mixed_precision": "bf16",
    "save_every_n_epochs": 2,
    "max_train_epochs": 10,
    "network_dim": 32,
    "network_alpha": 16,
    "learning_rate": 0.0001,
    "optimizer_type": "AdamW8bit",
    "lr_scheduler": "cosine",
    "gradient_checkpointing": True,
    "cache_latents": True,
    "max_data_loader_n_workers": 2,
    "persistent_data_loader_workers": True,
    "save_state": True,
    "seed": 42,
}

FAMILY_DEFAULTS = {
    "SD 1.x / 2.x": {"network_module": "networks.lora", "network_alpha": 16},
    "SDXL": {"network_module": "networks.lora", "network_train_unet_only": True,
             "cache_text_encoder_outputs": True},
    "SD3": {"network_module": "networks.lora_sd3", "cache_text_encoder_outputs": True},
    "FLUX": {"network_module": "networks.lora_flux", "network_train_unet_only": True,
             "cache_text_encoder_outputs": True, "timestep_sampling": "shift",
             "discrete_flow_shift": 3.1582, "model_prediction_type": "raw", "guidance_scale": 1.0,
             "optimizer_type": "AdamW8bit", "fp8_base": True},
    "Lumina": {"network_module": "networks.lora_lumina", "cache_text_encoder_outputs": True},
    "HunyuanImage": {"network_module": "networks.lora_hunyuan_image", "cache_text_encoder_outputs": True},
    # A tested starting point for Anima character LoRAs.
    "Anima": {
        "network_module": "networks.lora_anima", "network_dim": 32, "network_alpha": 32,
        "max_train_epochs": 20, "unsloth_offload_checkpointing": True,
        "cache_text_encoder_outputs": True, "network_train_unet_only": True,
        "optimizer_type": "pytorch_optimizer.CAME",
        "optimizer_args": ["betas=(0.9,0.99,0.999)", "weight_decay=0.001", "eps1=1e-30", "eps2=1e-16"],
        "lr_scheduler": "polynomial", "timestep_sampling": "sigmoid", "discrete_flow_shift": 3,
        "sigmoid_scale": 1.0, "max_grad_norm": 1, "huber_schedule": "snr", "huber_c": 0.1,
        "huber_scale": 1.0,
    },
}

DEFAULT_DATASET = {
    "resolution": [1024, 1024],
    "enable_bucket": True,
    "bucket_reso_steps": 64,
    "min_bucket_reso": 512,
    "max_bucket_reso": 2048,
    "caption_extension": ".txt",
    "shuffle_caption": False,
    "keep_tokens": 0,
    "flip_aug": False,
    "batch_size": 2,
    "subsets": [{"image_dir": "", "num_repeats": 2}],
}


def defaults_for(family, schema_keys):
    vals = dict(COMMON_DEFAULTS)
    vals.update(FAMILY_DEFAULTS.get(family, {}))
    return {k: v for k, v in vals.items() if k in schema_keys}
