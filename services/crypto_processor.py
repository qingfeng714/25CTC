from ascon import ascon_encrypt
from fpe_ff3 import FF3Cipher
import json

class HybridCryptoProcessor:
    def __init__(self, kms_endpoint: str):
        self.kms = KMSService(kms_endpoint)
        
    def protect_dicom(self, dicom_path: str, roi_mask: np.ndarray) -> str:
        """渐进式DICOM加密"""
        import pydicom
        ds = pydicom.dcmread(dicom_path)
        
        # 元数据加密
        for tag in ['PatientID', 'PatientName']:
            if tag in ds:
                ds[tag].value = self._encrypt_meta(ds[tag].value)
        
        # 像素数据部分加密
        pixel_data = ds.pixel_array
        non_roi = pixel_data * (1 - roi_mask)
        encrypted_pixels = ascon_encrypt(
            key=self.kms.get_key('pixel'),
            data=non_roi.tobytes(),
            ad=b'',
            nonce=b''
        )
        ds.PixelData = (pixel_data * roi_mask + np.frombuffer(encrypted_pixels)).tobytes()
        
        return ds

    def fpe_transform(self, text: str, phi_type: str) -> str:
        """格式保留加密"""
        cipher = FF3Cipher(
            key=self.kms.get_key('fpe'),
            tweak=phi_type.encode(),
            radix=10 if phi_type == 'PHONE' else 36,
            min_len=6,
            max_len=20
        )
        return cipher.encrypt(text)