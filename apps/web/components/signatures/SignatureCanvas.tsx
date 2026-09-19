"use client";

import React, { useRef, useState, useEffect } from "react";
import { Check, Eraser, Type, PenTool, Upload, Image as ImageIcon } from "lucide-react";

interface SignatureCanvasProps {
  onSave: (dataUrl: string) => void;
  onCancel?: () => void;
}

const SCRIPT_FONTS = [
  { id: "cursive", name: "Cursive Classic", fontFamily: "'Brush Script MT', 'Dancing Script', cursive, serif", fontStyle: "italic 32px Georgia, serif" },
  { id: "handwriting", name: "Signature Script", fontFamily: "'Great Vibes', 'Caveat', cursive", fontStyle: "30px 'Courier New', monospace" },
  { id: "formal", name: "Formal Script", fontFamily: "'Zapfino', 'Snell Roundhand', cursive", fontStyle: "bold italic 28px serif" },
  { id: "clean", name: "Clean Modern", fontFamily: "Inter, sans-serif", fontStyle: "500 28px Inter, sans-serif" },
  { id: "mono", name: "Monospace Stamp", fontFamily: "monospace", fontStyle: "bold 26px monospace" },
] as const;

export function SignatureCanvas({ onSave, onCancel }: SignatureCanvasProps) {
  const [activeTab, setActiveTab] = useState<"draw" | "type" | "upload">("draw");
  const [typedName, setTypedName] = useState("");
  const [selectedFontIndex, setSelectedFontIndex] = useState<number>(0);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isDrawing = useRef(false);

  useEffect(() => {
    if (activeTab !== "draw") return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#97192C"; // Brand Burgundy ink
  }, [activeTab]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    isDrawing.current = true;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const touch = "touches" in e ? e.touches[0] : null;
    const clientX = touch ? touch.clientX : (e as React.MouseEvent).clientX;
    const clientY = touch ? touch.clientY : (e as React.MouseEvent).clientY;

    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const touch = "touches" in e ? e.touches[0] : null;
    const clientX = touch ? touch.clientX : (e as React.MouseEvent).clientX;
    const clientY = touch ? touch.clientY : (e as React.MouseEvent).clientY;

    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
  };

  const stopDrawing = () => {
    isDrawing.current = false;
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        setUploadedImage(event.target.result as string);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    if (activeTab === "draw") {
      const canvas = canvasRef.current;
      if (!canvas) return;
      onSave(canvas.toDataURL("image/png"));
    } else if (activeTab === "type") {
      if (!typedName.trim()) return;
      const font = SCRIPT_FONTS[selectedFontIndex] || SCRIPT_FONTS[0];
      const tempCanvas = document.createElement("canvas");
      tempCanvas.width = 450;
      tempCanvas.height = 140;
      const ctx = tempCanvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#97192C";
        ctx.font = font.fontStyle;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(typedName, tempCanvas.width / 2, tempCanvas.height / 2);
        onSave(tempCanvas.toDataURL("image/png"));
      }
    } else if (activeTab === "upload") {
      if (!uploadedImage) return;
      onSave(uploadedImage);
    }
  };

  const currentFont = SCRIPT_FONTS[selectedFontIndex] || SCRIPT_FONTS[0];

  return (
    <div className="bg-secondary-background border-2 border-border rounded-base p-4 shadow-shadow max-w-lg w-full">
      <div className="flex items-center justify-between border-b-2 border-border pb-3 mb-4">
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTab("draw")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base text-xs font-bold font-heading transition-all ${
              activeTab === "draw"
                ? "bg-burgundy text-white shadow-shadow"
                : "bg-secondary-background text-foreground border border-border"
            }`}
          >
            <PenTool className="w-3.5 h-3.5" /> Draw
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("type")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base text-xs font-bold font-heading transition-all ${
              activeTab === "type"
                ? "bg-burgundy text-white shadow-shadow"
                : "bg-secondary-background text-foreground border border-border"
            }`}
          >
            <Type className="w-3.5 h-3.5" /> Type
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("upload")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-base text-xs font-bold font-heading transition-all ${
              activeTab === "upload"
                ? "bg-burgundy text-white shadow-shadow"
                : "bg-secondary-background text-foreground border border-border"
            }`}
          >
            <Upload className="w-3.5 h-3.5" /> Upload
          </button>
        </div>
        {activeTab === "draw" && (
          <button
            type="button"
            onClick={clearCanvas}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold font-heading text-burgundy hover:bg-burgundy/10 rounded-base"
          >
            <Eraser className="w-3.5 h-3.5" /> Clear
          </button>
        )}
      </div>

      {activeTab === "draw" && (
        <div className="border-2 border-dashed border-[#A09F9D] rounded-base bg-secondary-background overflow-hidden touch-none mb-4">
          <canvas
            ref={canvasRef}
            width={450}
            height={160}
            onMouseDown={startDrawing}
            onMouseMove={draw}
            onMouseUp={stopDrawing}
            onMouseLeave={stopDrawing}
            onTouchStart={startDrawing}
            onTouchMove={draw}
            onTouchEnd={stopDrawing}
            className="w-full cursor-crosshair"
          />
        </div>
      )}

      {activeTab === "type" && (
        <div className="space-y-4 mb-4">
          <input
            type="text"
            placeholder="Type your full name..."
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            className="w-full px-3 py-2 border-2 border-border rounded-base text-sm font-heading bg-secondary-background font-medium focus:outline-none focus:ring-2 focus:ring-burgundy"
          />
          <div className="flex gap-2 overflow-x-auto pb-1">
            {SCRIPT_FONTS.map((font, idx) => (
              <button
                key={font.id}
                type="button"
                onClick={() => setSelectedFontIndex(idx)}
                className={`px-2.5 py-1 text-[11px] font-bold font-heading rounded-base border shrink-0 transition-all ${
                  selectedFontIndex === idx
                    ? "bg-burgundy text-white border-border"
                    : "bg-secondary-background text-foreground border-[#D0CFCE] hover:bg-gray-100"
                }`}
              >
                {font.name}
              </button>
            ))}
          </div>
          <div className="border-2 border-border rounded-base p-4 bg-secondary-background min-h-[100px] flex items-center justify-center">
            <span
              style={{ fontFamily: currentFont.fontFamily }}
              className="text-2xl text-burgundy italic"
            >
              {typedName || "Signature Preview"}
            </span>
          </div>
        </div>
      )}

      {activeTab === "upload" && (
        <div className="space-y-4 mb-4">
          <label className="border-2 border-dashed border-border rounded-base p-6 bg-secondary-background flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors">
            <ImageIcon className="w-8 h-8 text-muted-foreground mb-2" />
            <span className="text-xs font-bold font-heading text-foreground">Upload image of wet signature</span>
            <span className="text-[10px] text-muted-foreground mt-1">PNG, JPG or WEBP (Max 5MB)</span>
            <input
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
          </label>
          {uploadedImage && (
            <div className="border-2 border-border rounded-base p-3 bg-secondary-background flex items-center justify-center max-h-32 overflow-hidden">
              <img src={uploadedImage} alt="Uploaded Signature" className="max-h-24 object-contain" />
            </div>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-[#D0CFCE]">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-xs font-bold font-heading border-2 border-border rounded-base bg-secondary-background text-foreground hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleSave}
          disabled={
            (activeTab === "type" && !typedName.trim()) ||
            (activeTab === "upload" && !uploadedImage)
          }
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold font-heading bg-orange text-foreground border-2 border-border rounded-base shadow-shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none disabled:opacity-40 transition-all"
        >
          <Check className="w-4 h-4" /> Adopt & Sign
        </button>
      </div>
    </div>
  );
}
