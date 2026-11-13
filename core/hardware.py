import os
import logging
import psutil
import torch

logger = logging.getLogger(__name__)

class HardwareManager:

    def __init__(self):
        self.hardware_info = self._detect_environment()
        self._apply_optimizations()

    def _detect_environment(self) -> dict:
        info = {
            'has_gpu': False,
            'device': 'cpu',
            'device_name': 'Standard CPU',
            'vram_mb': 0,
            'cpu_cores': psutil.cpu_count(logical=False) or 4,
            'ram_gb': round(psutil.virtual_memory().total / (1024 ** 3), 1),
            'recommended_imgsz': 640,
            'recommended_stride': 1,
            'half_precision': False
        }

        if torch.cuda.is_available():
            try:
                gpu_name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
                info['has_gpu'] = True
                info['device'] = 'cuda:0'
                info['device_name'] = gpu_name
                info['vram_mb'] = int(vram)
                info['recommended_imgsz'] = 640
                info['recommended_stride'] = 1
                info['half_precision'] = True
                logger.info(f"[HARDWARE] GPU Terdeteksi: {gpu_name} ({int(vram)} MB VRAM) -> Mode GPU Aktif")
                return info
            except Exception as e:
                logger.warning(f"[HARDWARE] Gagal inisialisasi CUDA: {e}. Beralih ke CPU.")

        info['has_gpu'] = False
        info['device'] = 'cpu'
        info['device_name'] = f"CPU ({info['cpu_cores']} Physical Cores, {info['ram_gb']} GB RAM)"
        info['half_precision'] = False

        if info['cpu_cores'] >= 8:
            info['recommended_imgsz'] = 640
            info['recommended_stride'] = 1
        elif info['cpu_cores'] >= 4:
            info['recommended_imgsz'] = 480
            info['recommended_stride'] = 1
        else:

            info['recommended_imgsz'] = 384
            info['recommended_stride'] = 2

        logger.info(
            f"[HARDWARE] Mode CPU Aktif: {info['device_name']}. "
            f"Adaptive Resolution: {info['recommended_imgsz']}p, Stride: {info['recommended_stride']}"
        )
        return info

    def _apply_optimizations(self):
        if not self.hardware_info['has_gpu']:
            threads = max(1, min(self.hardware_info['cpu_cores'], 8))
            torch.set_num_threads(threads)
            os.environ["OMP_NUM_THREADS"] = str(threads)
            os.environ["MKL_NUM_THREADS"] = str(threads)
            logger.info(f"[HARDWARE] CPU Thread Pool diset ke {threads} threads.")

    def get_device(self) -> str:
        return self.hardware_info['device']

    def get_imgsz(self) -> int:
        return self.hardware_info['recommended_imgsz']

    def is_half_precision(self) -> bool:
        return self.hardware_info['half_precision']

    def get_summary(self) -> dict:
        vm = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        res = dict(self.hardware_info)
        res['live_cpu_percent'] = cpu_pct
        res['live_ram_percent'] = vm.percent
        return res

hardware = HardwareManager()
