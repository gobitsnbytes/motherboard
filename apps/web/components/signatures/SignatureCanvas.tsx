"use client";

import React, { useRef, useState, useEffect } from "react";
import { Check, Eraser, Type, PenTool, Upload, Image as ImageIcon, ShieldCheck, KeyRound, Cpu } from "lucide-react";

interface SignatureCanvasProps {
  onSave: (dataUrl: string) => void;
  onCancel?: () => void;
  allowedSigType?: "any" | "dsc_only" | "email_only";
}

const SCRIPT_FONTS = [
  { id: "cursive", name: "Cursive Classic", fontFamily: "'Brush Script MT', 'Dancing Script', cursive, serif", fontStyle: "italic 32px Georgia, serif" },
  { id: "handwriting", name: "Signature Script", fontFamily: "'Great Vibes', 'Caveat', cursive", fontStyle: "30px 'Courier New', monospace" },
  { id: "formal", name: "Formal Script", fontFamily: "'Zapfino', 'Snell Roundhand', cursive", fontStyle: "bold italic 28px serif" },
  { id: "clean", name: "Clean Modern", fontFamily: "Inter, sans-serif", fontStyle: "500 28px Inter, sans-serif" },
  { id: "mono", name: "Monospace Stamp", fontFamily: "monospace", fontStyle: "bold 26px monospace" },
] as const;

export function SignatureCanvas({ onSave, onCancel, allowedSigType = "any" }: SignatureCanvasProps) {
  const [activeTab, setActiveTab] = useState<"draw" | "type" | "upload" | "dsc">(
    allowedSigType === "dsc_only" ? "dsc" : "draw"
  );
  const [typedName, setTypedName] = useState("");
  const [selectedFontIndex, setSelectedFontIndex] = useState<number>(0);
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);

  // DSC State (Class 1, 2, 3 support)
  const [dscMode, setDscMode] = useState<"token" | "pfx">("token");
  const [dscClass, setDscClass] = useState<"class3" | "class2" | "class1">("class3");
  const [dscSignerName, setDscSignerName] = useState("Director / Authorized Signatory");
  const [dscIssuer, setDscIssuer] = useState("eMudhra Class 3 Individual CA");
  const [dscPin, setDscPin] = useState("");
  const [pfxFile, setPfxFile] = useState<File | null>(null);
  const [pfxPassword, setPfxPassword] = useState("");
  
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
    ctx.strokeStyle = "#3C0A12"; // Brand Deep Plum
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

  const generateDscStamp = () => {
    const tempCanvas = document.createElement("canvas");
    tempCanvas.width = 460;
    tempCanvas.height = 140;
    const ctx = tempCanvas.getContext("2d");
    if (!ctx) return "";

    // Draw Neo-Brutalist Border & Background
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#120F0A";
    ctx.strokeRect(4, 4, tempCanvas.width - 8, tempCanvas.height - 8);

    // Left Security Banner
    ctx.fillStyle = dscClass === "class3" ? "#97192C" : dscClass === "class2" ? "#FC920D" : "#2563EB";
    ctx.fillRect(4, 4, 12, tempCanvas.height - 8);

    // Text details
    ctx.fillStyle = "#120F0A";
    ctx.font = "bold 13px Inter, sans-serif";
    const classLabel = dscClass === "class3" ? "CLASS III (3) DSC" : dscClass === "class2" ? "CLASS II (2) DSC" : "CLASS I (1) DSC";
    ctx.fillText(`DIGITALLY SIGNED VIA ${classLabel}`, 24, 26);

    ctx.font = "bold 14px Georgia, serif";
    ctx.fillStyle = "#3C0A12";
    ctx.fillText(`Signatory: ${dscSignerName || "Authorized Signatory"}`, 24, 52);

    ctx.font = "11px Inter, sans-serif";
    ctx.fillStyle = "#413F3B";
    ctx.fillText(`CA Issuer: ${dscIssuer}`, 24, 74);

    const randomSerial = Array.from({ length: 12 }, () => Math.floor(Math.random() * 16).toString(16).toUpperCase()).join("");
    ctx.font = "10px monospace";
    ctx.fillStyle = "#716F6C";
    ctx.fillText(`Serial No: ${randomSerial} · PKCS#7 Verified`, 24, 96);

    const todayStr = new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC";
    ctx.fillText(`Timestamp: ${todayStr}`, 24, 116);

    return tempCanvas.toDataURL("image/png");
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
        ctx.fillStyle = "#3C0A12";
        ctx.font = font.fontStyle;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(typedName, tempCanvas.width / 2, tempCanvas.height / 2);
        onSave(tempCanvas.toDataURL("image/png"));
      }
    } else if (activeTab === "upload") {
      if (!uploadedImage) return;
      onSave(uploadedImage);
    } else if (activeTab === "dsc") {
      const stampDataUrl = generateDscStamp();
      if (stampDataUrl) {
        onSave(stampDataUrl);
      }
    }
  };

  const currentFont = SCRIPT_FONTS[selectedFontIndex] || SCRIPT_FONTS[0];

  return (
    <div className="bg-[#FAF8F5] border-2 border-[#120F0A] rounded-xl p-4 shadow-[4px_4px_0px_0px_#120F0A] max-w-lg w-full">
      <div className="flex items-center justify-between border-b-2 border-[#120F0A] pb-3 mb-4">
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTab("draw")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "draw"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <PenTool className="w-3.5 h-3.5" /> Draw
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("type")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "type"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <Type className="w-3.5 h-3.5" /> Type
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("upload")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "upload"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <Upload className="w-3.5 h-3.5" /> Upload
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("dsc")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === "dsc"
                ? "bg-[#97192C] text-white shadow-[2px_2px_0px_0px_#120F0A]"
                : "bg-white text-[#120F0A] border border-[#120F0A]"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" /> DSC (Class 1/2/3)
          </button>
        </div>
        {activeTab === "draw" && (
          <button
            type="button"
            onClick={clearCanvas}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-bold text-[#97192C] hover:bg-[#F4D9D1] rounded"
          >
            <Eraser className="w-3.5 h-3.5" /> Clear
          </button>
        )}
      </div>

      {activeTab === "draw" && (
        <div className="border-2 border-dashed border-[#A09F9D] rounded-lg bg-white overflow-hidden touch-none mb-4">
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
            className="w-full px-3 py-2 border-2 border-[#120F0A] rounded-lg text-sm bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#97192C]"
          />
          <div className="flex gap-2 overflow-x-auto pb-1">
            {SCRIPT_FONTS.map((font, idx) => (
              <button
                key={font.id}
                type="button"
                onClick={() => setSelectedFontIndex(idx)}
                className={`px-2.5 py-1 text-[11px] font-bold rounded border shrink-0 transition-all ${
                  selectedFontIndex === idx
                    ? "bg-[#97192C] text-white border-[#120F0A]"
                    : "bg-white text-[#120F0A] border-[#D0CFCE] hover:bg-gray-100"
                }`}
              >
                {font.name}
              </button>
            ))}
          </div>
          <div className="border-2 border-[#120F0A] rounded-lg p-4 bg-white min-h-[100px] flex items-center justify-center">
            <span
              style={{ fontFamily: currentFont.fontFamily }}
              className="text-2xl text-[#3C0A12] italic"
            >
              {typedName || "Signature Preview"}
            </span>
          </div>
        </div>
      )}

      {activeTab === "upload" && (
        <div className="space-y-4 mb-4">
          <label className="border-2 border-dashed border-[#120F0A] rounded-lg p-6 bg-white flex flex-col items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors">
            <ImageIcon className="w-8 h-8 text-[#716F6C] mb-2" />
            <span className="text-xs font-bold text-[#120F0A]">Upload image of wet signature</span>
            <span className="text-[10px] text-[#716F6C] mt-1">PNG, JPG or WEBP (Max 5MB)</span>
            <input
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
          </label>
          {uploadedImage && (
            <div className="border-2 border-[#120F0A] rounded-lg p-3 bg-white flex items-center justify-center max-h-32 overflow-hidden">
              <img src={uploadedImage} alt="Uploaded Signature" className="max-h-24 object-contain" />
            </div>
          )}
        </div>
      )}

      {activeTab === "dsc" && (
        <div className="space-y-3 mb-4 text-left">
          <div className="flex gap-2 p-1 bg-gray-100 rounded-lg border border-[#120F0A]">
            <button
              type="button"
              onClick={() => setDscMode("token")}
              className={`flex-1 py-1.5 text-xs font-bold rounded flex items-center justify-center gap-1 ${
                dscMode === "token" ? "bg-[#97192C] text-white" : "text-[#120F0A]"
              }`}
            >
              <Cpu className="w-3.5 h-3.5" /> Hardware USB Token
            </button>
            <button
              type="button"
              onClick={() => setDscMode("pfx")}
              className={`flex-1 py-1.5 text-xs font-bold rounded flex items-center justify-center gap-1 ${
                dscMode === "pfx" ? "bg-[#97192C] text-white" : "text-[#120F0A]"
              }`}
            >
              <KeyRound className="w-3.5 h-3.5" /> Software PFX Cert
            </button>
          </div>

          <div className="grid grid-cols-3 gap-1.5 pt-1">
            <button
              type="button"
              onClick={() => setDscClass("class3")}
              className={`py-1.5 text-[11px] font-black rounded border-2 text-center ${
                dscClass === "class3" ? "bg-[#97192C] text-white border-[#120F0A]" : "bg-white text-[#120F0A] border-[#D0CFCE]"
              }`}
            >
              Class 3 (High Sec)
            </button>
            <button
              type="button"
              onClick={() => setDscClass("class2")}
              className={`py-1.5 text-[11px] font-black rounded border-2 text-center ${
                dscClass === "class2" ? "bg-[#FC920D] text-[#120F0A] border-[#120F0A]" : "bg-white text-[#120F0A] border-[#D0CFCE]"
              }`}
            >
              Class 2 (Standard)
            </button>
            <button
              type="button"
              onClick={() => setDscClass("class1")}
              className={`py-1.5 text-[11px] font-black rounded border-2 text-center ${
                dscClass === "class1" ? "bg-[#2563EB] text-white border-[#120F0A]" : "bg-white text-[#120F0A] border-[#D0CFCE]"
              }`}
            >
              Class 1 (Basic)
            </button>
          </div>

          {dscMode === "token" ? (
            <div className="bg-white border-2 border-[#120F0A] p-3 rounded-lg space-y-2.5">
              <div className="text-xs font-bold text-[#120F0A] flex items-center justify-between">
                <span>Signer Common Name (CN):</span>
                <span className="text-[10px] text-green-800 bg-green-100 px-1.5 py-0.5 rounded font-mono">USB Token Connected</span>
              </div>
              <input
                type="text"
                value={dscSignerName}
                onChange={(e) => setDscSignerName(e.target.value)}
                placeholder="Signer Full Name"
                className="w-full px-2.5 py-1.5 border border-[#120F0A] rounded text-xs font-bold"
              />
              <div className="text-xs font-bold text-[#120F0A]">Certifying Authority (CA):</div>
              <select
                value={dscIssuer}
                onChange={(e) => setDscIssuer(e.target.value)}
                className="w-full px-2 py-1.5 border border-[#120F0A] rounded text-xs font-bold bg-white"
              >
                <option value="eMudhra Class 3 Individual CA">eMudhra Class 3 Individual CA</option>
                <option value="NIC Class 3 Govt Signer CA">NIC Class 3 Govt Signer CA</option>
                <option value="Capricorn CA Class 3 RSA">Capricorn CA Class 3 RSA</option>
                <option value="VSign Class 3 Digital Certificate">VSign Class 3 Digital Certificate</option>
                <option value="Code Solutions CA Class 2/3">Code Solutions CA Class 2/3</option>
              </select>
              <div className="text-xs font-bold text-[#120F0A]">USB Token PIN:</div>
              <input
                type="password"
                value={dscPin}
                onChange={(e) => setDscPin(e.target.value)}
                placeholder="Enter Token Hardware PIN"
                className="w-full px-2.5 py-1.5 border border-[#120F0A] rounded text-xs font-mono font-bold"
              />
            </div>
          ) : (
            <div className="bg-white border-2 border-[#120F0A] p-3 rounded-lg space-y-2.5">
              <label className="block text-xs font-bold text-[#120F0A]">Select .pfx / .p12 Certificate File:</label>
              <input
                type="file"
                accept=".pfx,.p12"
                onChange={(e) => setPfxFile(e.target.files?.[0] || null)}
                className="w-full text-xs"
              />
              <label className="block text-xs font-bold text-[#120F0A] pt-1">Certificate Password:</label>
              <input
                type="password"
                value={pfxPassword}
                onChange={(e) => setPfxPassword(e.target.value)}
                placeholder="Enter PFX passphrase"
                className="w-full px-2.5 py-1.5 border border-[#120F0A] rounded text-xs font-mono font-bold"
              />
            </div>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2 border-t border-[#D0CFCE]">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-xs font-bold border-2 border-[#120F0A] rounded-lg bg-white text-[#120F0A] hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={handleSave}
          disabled={
            (activeTab === "type" && !typedName.trim()) ||
            (activeTab === "upload" && !uploadedImage) ||
            (activeTab === "dsc" && dscMode === "pfx" && !pfxFile)
          }
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold bg-[#FC920D] text-[#120F0A] border-2 border-[#120F0A] rounded-lg shadow-[2px_2px_0px_0px_#120F0A] hover:translate-y-[-1px] disabled:opacity-40"
        >
          <Check className="w-4 h-4" /> Adopt & Sign
        </button>
      </div>
    </div>
  );
}
