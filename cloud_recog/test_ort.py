import onnxruntime as ort

providers = ort.get_available_providers()
print("Available providers:", providers)
