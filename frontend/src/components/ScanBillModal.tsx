'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Camera, X, Flashlight, Plus, Check, Trash2, RefreshCw, Upload, Shield, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface ScanBillModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapturePages: (files: File[]) => void;
}

export function ScanBillModal({ isOpen, onClose, onCapturePages }: ScanBillModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputFallbackRef = useRef<HTMLInputElement>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [capturedPages, setCapturedPages] = useState<{ dataUrl: string; file: File }[]>([]);
  const [torchSupported, setTorchSupported] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [permissionState, setPermissionState] = useState<'PROMPT' | 'REQUESTING' | 'GRANTED' | 'DENIED'>('PROMPT');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      stopCamera();
      setCapturedPages([]);
      setCameraError(null);
      setPermissionState('PROMPT');
      return;
    }
  }, [isOpen]);

  const requestCameraAccess = async () => {
    setPermissionState('REQUESTING');
    setCameraError(null);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera access is not supported by your browser. Please use file upload.');
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 3840, min: 1920 },
          height: { ideal: 2160, min: 1080 }
        },
        audio: false
      });

      setStream(mediaStream);
      setPermissionState('GRANTED');

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play().catch(() => {});
      }

      // Check torch capability
      const track = mediaStream.getVideoTracks()[0];
      const capabilities = track.getCapabilities ? (track.getCapabilities() as any) : {};
      if (capabilities.torch) {
        setTorchSupported(true);
      }
    } catch (err: any) {
      console.warn('Camera initialization error:', err);
      setPermissionState('DENIED');
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCameraError('Camera permission was denied. Please allow camera permissions in your browser address bar, or upload your invoice file directly.');
      } else {
        setCameraError(err.message || 'Unable to access your device camera. Please upload your invoice bill directly.');
      }
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
    setTorchOn(false);
  };

  const toggleTorch = async () => {
    if (!stream) return;
    const track = stream.getVideoTracks()[0];
    if (track && torchSupported) {
      try {
        const nextState = !torchOn;
        await (track as any).applyConstraints({
          advanced: [{ torch: nextState }]
        });
        setTorchOn(nextState);
      } catch (e) {
        console.warn('Failed to toggle flashlight:', e);
      }
    }
  };

  const captureFrame = () => {
    if (!videoRef.current || !canvasRef.current) return;
    setIsCapturing(true);

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1920;
    canvas.height = video.videoHeight || 1080;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      setIsCapturing(false);
      return;
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setIsCapturing(false);
          return;
        }

        const pageNum = capturedPages.length + 1;
        const file = new File([blob], `Bill_Page_${pageNum}.jpg`, { type: 'image/jpeg' });
        const dataUrl = canvas.toDataURL('image/jpeg', 0.92);

        setCapturedPages((prev) => [...prev, { dataUrl, file }]);
        setIsCapturing(false);
      },
      'image/jpeg',
      0.92
    );
  };

  const handleRemovePage = (index: number) => {
    setCapturedPages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFallbackFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCapturedPages((prev) => [
            ...prev,
            { dataUrl: event.target!.result as string, file }
          ]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  const handleFinish = () => {
    if (capturedPages.length === 0) return;
    const files = capturedPages.map((p) => p.file);
    stopCamera();
    onCapturePages(files);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col animate-fadeIn select-none">
      {/* Top Controls Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-black/80 backdrop-blur-md z-20 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <Camera className="w-5 h-5 text-emerald-400" />
          <span className="text-white font-extrabold text-sm tracking-wide">Scan Invoice Bill</span>
          {capturedPages.length > 0 && (
            <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs px-2 py-0.5 rounded-full font-mono font-bold">
              {capturedPages.length} {capturedPages.length === 1 ? 'Page' : 'Pages'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {torchSupported && permissionState === 'GRANTED' && (
            <button
              type="button"
              onClick={toggleTorch}
              className={`p-2 rounded-full border transition-all ${
                torchOn ? 'bg-amber-400 text-black border-amber-300' : 'bg-neutral-800 text-neutral-300 border-neutral-700'
              }`}
              title="Toggle Flashlight"
            >
              <Flashlight className="w-4 h-4" />
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-full bg-neutral-800 text-neutral-400 hover:text-white border border-neutral-700 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Viewport */}
      <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden">
        
        {/* Pre-Flight Camera Permission Dialog (PRD Requirement) */}
        {permissionState === 'PROMPT' && (
          <div className="text-center p-6 max-w-md bg-neutral-900 border border-neutral-800 rounded-3xl text-neutral-200 space-y-5 m-4 shadow-2xl animate-scaleUp">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-glow-brand">
              <Camera className="w-8 h-8" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-white tracking-tight">Camera Permission Required</h3>
              <p className="text-xs text-neutral-400 leading-relaxed">
                Kangra Hub requires camera access to scan, auto-align, and crop your Sales & Purchase paper bills directly from your device.
              </p>
            </div>

            <div className="p-3 bg-neutral-800/80 rounded-xl border border-neutral-700/60 text-[11px] text-neutral-300 flex items-center gap-2.5 text-left">
              <Shield className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Images are processed in memory for OCR and never stored permanently on disk.</span>
            </div>

            <div className="space-y-2.5 pt-2">
              <Button
                type="button"
                variant="primary"
                onClick={requestCameraAccess}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs py-3"
              >
                Allow & Start Camera
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputFallbackRef.current?.click()}
                className="w-full border-neutral-700 text-neutral-300 hover:text-white hover:bg-neutral-800 text-xs py-3"
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload Invoice File / Photo Instead
              </Button>
            </div>

            <input
              type="file"
              ref={fileInputFallbackRef}
              accept="image/*,.pdf"
              capture="environment"
              multiple
              onChange={handleFallbackFile}
              className="hidden"
            />
          </div>
        )}

        {/* Requesting State */}
        {permissionState === 'REQUESTING' && (
          <div className="text-center p-6 text-neutral-300 space-y-3">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs font-semibold">Connecting to camera...</p>
          </div>
        )}

        {/* Camera Permission Denied / Error State */}
        {permissionState === 'DENIED' && (
          <div className="text-center p-6 max-w-sm bg-neutral-900 border border-neutral-800 rounded-3xl text-neutral-200 space-y-4 m-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
              <AlertCircle className="w-6 h-6" />
            </div>
            <p className="text-xs font-medium text-neutral-300 leading-relaxed">
              {cameraError || 'Unable to access your device camera. Please upload your invoice bill directly.'}
            </p>
            <div className="space-y-2 pt-2">
              <Button
                type="button"
                variant="primary"
                onClick={() => fileInputFallbackRef.current?.click()}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
              >
                <Upload className="w-4 h-4 mr-2" />
                Upload Bill File or Photo
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={requestCameraAccess}
                className="w-full border-neutral-700 text-neutral-300 hover:text-white text-xs"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Try Camera Again
              </Button>
            </div>
            <input
              type="file"
              ref={fileInputFallbackRef}
              accept="image/*,.pdf"
              capture="environment"
              multiple
              onChange={handleFallbackFile}
              className="hidden"
            />
          </div>
        )}

        {/* Active Camera Viewport */}
        {permissionState === 'GRANTED' && (
          <>
            <video
              ref={videoRef}
              playsInline
              autoPlay
              muted
              className="w-full h-full object-cover max-h-screen"
            />

            {/* Document Edge Alignment Overlay */}
            <div className="absolute inset-8 sm:inset-12 pointer-events-none border-2 border-emerald-400/60 rounded-2xl shadow-2xl flex flex-col justify-between p-4">
              <div className="flex justify-between">
                <div className="w-8 h-8 border-t-4 border-l-4 border-emerald-400 rounded-tl-xl -mt-1 -ml-1"></div>
                <div className="w-8 h-8 border-t-4 border-r-4 border-emerald-400 rounded-tr-xl -mt-1 -mr-1"></div>
              </div>

              <div className="text-center bg-black/60 backdrop-blur-sm py-1.5 px-4 rounded-full mx-auto text-emerald-300 font-bold text-xs shadow-md border border-emerald-500/20">
                Align bill edges inside the box
              </div>

              <div className="flex justify-between">
                <div className="w-8 h-8 border-b-4 border-l-4 border-emerald-400 rounded-bl-xl -mb-1 -ml-1"></div>
                <div className="w-8 h-8 border-b-4 border-r-4 border-emerald-400 rounded-br-xl -mb-1 -mr-1"></div>
              </div>
            </div>
          </>
        )}

        <canvas ref={canvasRef} className="hidden" />
      </div>

      {/* Captured Pages Strip (Horizontal Scroll) */}
      {capturedPages.length > 0 && (
        <div className="bg-neutral-950/90 backdrop-blur-md px-4 py-2 border-t border-neutral-800 flex items-center gap-3 overflow-x-auto z-20">
          {capturedPages.map((page, index) => (
            <div
              key={index}
              className="relative w-14 h-20 rounded-lg overflow-hidden border border-neutral-700 shrink-0 group bg-neutral-900"
            >
              <img src={page.dataUrl} alt={`Page ${index + 1}`} className="w-full h-full object-cover" />
              <div className="absolute top-0 left-0 bg-black/70 text-white text-[9px] px-1 font-mono font-bold rounded-br">
                {index + 1}
              </div>
              <button
                type="button"
                onClick={() => handleRemovePage(index)}
                className="absolute inset-0 bg-red-600/80 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Bottom Shutter & Action Bar */}
      {permissionState === 'GRANTED' && (
        <div className="px-6 py-5 bg-black/90 backdrop-blur-md border-t border-neutral-800 flex items-center justify-between z-20 safe-area-pb">
          {/* File Picker Fallback Button */}
          <button
            type="button"
            onClick={() => fileInputFallbackRef.current?.click()}
            className="flex flex-col items-center gap-1 text-neutral-400 hover:text-white transition-colors"
          >
            <Upload className="w-5 h-5" />
            <span className="text-[10px] font-semibold">Upload</span>
          </button>
          <input
            type="file"
            ref={fileInputFallbackRef}
            accept="image/*"
            capture="environment"
            multiple
            onChange={handleFallbackFile}
            className="hidden"
          />

          {/* Shutter Button */}
          <button
            type="button"
            onClick={captureFrame}
            disabled={isCapturing}
            className="w-16 h-16 rounded-full border-4 border-white flex items-center justify-center p-1 hover:scale-105 active:scale-95 transition-all shadow-glow-brand"
            aria-label="Capture page"
          >
            <div className={`w-full h-full rounded-full transition-colors ${isCapturing ? 'bg-amber-400 animate-pulse' : 'bg-white'}`} />
          </button>

          {/* Done / Finish Button */}
          {capturedPages.length > 0 ? (
            <button
              type="button"
              onClick={handleFinish}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-colors shadow-glow-brand"
            >
              <Check className="w-4 h-4" />
              <span>Done ({capturedPages.length})</span>
            </button>
          ) : (
            <div className="w-16" />
          )}
        </div>
      )}
    </div>
  );
}
