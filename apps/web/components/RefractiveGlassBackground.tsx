"use client";

import React, { useRef, useMemo, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useSpring } from "framer-motion";

const vertexShader = `
uniform float uTime;
uniform vec2 uMouse;
uniform float uMagneticStrength;

varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;
varying float vNoise;

// Procedural 3D Noise for liquid morphing
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i); 
  vec4 p = permute(permute(permute( 
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0)) 
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy,h.x);
  vec3 p1 = vec3(a0.zw,h.y);
  vec3 p2 = vec3(a1.xy,h.z);
  vec3 p3 = vec3(a1.zw,h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// 3D curl noise approximation for twisting fluid motion
vec3 curlNoise(vec3 p) {
    float e = 0.1;
    vec3 dx = vec3(e, 0.0, 0.0);
    vec3 dy = vec3(0.0, e, 0.0);
    vec3 dz = vec3(0.0, 0.0, e);
    
    vec3 p_x0 = vec3(snoise(p - dx), snoise(p - dx + vec3(12.3)), snoise(p - dx + vec3(24.5)));
    vec3 p_x1 = vec3(snoise(p + dx), snoise(p + dx + vec3(12.3)), snoise(p + dx + vec3(24.5)));
    vec3 p_y0 = vec3(snoise(p - dy), snoise(p - dy + vec3(12.3)), snoise(p - dy + vec3(24.5)));
    vec3 p_y1 = vec3(snoise(p + dy), snoise(p + dy + vec3(12.3)), snoise(p + dy + vec3(24.5)));
    vec3 p_z0 = vec3(snoise(p - dz), snoise(p - dz + vec3(12.3)), snoise(p - dz + vec3(24.5)));
    vec3 p_z1 = vec3(snoise(p + dz), snoise(p + dz + vec3(12.3)), snoise(p + dz + vec3(24.5)));
    
    float x = p_y1.z - p_y0.z - p_z1.y + p_z0.y;
    float y = p_z1.x - p_z0.x - p_x1.z + p_x0.z;
    float z = p_x1.y - p_x0.y - p_y1.x + p_y0.x;
    
    return normalize(vec3(x, y, z) / (2.0 * e));
}

void main() {
  vUv = uv;
  
  // Highly dynamic, fluid morphing using fractal noise and curl
  float n1 = snoise(position * 1.5 + uTime * 0.3) * 0.25;
  float n2 = snoise(position * 3.0 - uTime * 0.4) * 0.1;
  float n3 = snoise(position * 6.0 + uTime * 0.5) * 0.05;
  
  vNoise = n1 + n2 + n3;
  
  // Twist the position using curl noise for a swirling liquid effect
  vec3 curl = curlNoise(position * 0.8 + uTime * 0.1);
  vec3 displacedPosition = position + normal * vNoise + curl * 0.15;
  
  // Magnetic cursor physics mapping (intense pull)
  vec3 mouseWorld = vec3(uMouse.x * 4.0, uMouse.y * 4.0, 0.0);
  float dist = distance(displacedPosition, mouseWorld);
  float influence = exp(-dist * dist * 0.8) * uMagneticStrength;
  
  // Suck the liquid towards the mouse cursor dramatically
  vec3 dir = normalize(mouseWorld - displacedPosition);
  displacedPosition += dir * influence * 0.6;
  
  vec4 modelPosition = modelMatrix * vec4(displacedPosition, 1.0);
  vec4 mvPosition = viewMatrix * modelPosition;
  
  // Normal recalculation based on displacement gradients (cheap approximation)
  // We use the displacement direction as a normal perturbator to get crazy caustic reflections
  vec3 perturb = normalize(displacedPosition - position);
  vNormal = normalize(normalMatrix * normal + perturb * 0.8 + dir * influence * 1.5);
  
  vViewPosition = -mvPosition.xyz;
  vWorldPosition = modelPosition.xyz;
  
  gl_Position = projectionMatrix * mvPosition;
}
`;

const fragmentShader = `
uniform float uTime;
uniform vec2 uResolution;

varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;
varying float vNoise;

// Reuse snoise in fragment for internal volumetric texture
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i); 
  vec4 p = permute(permute(permute( 
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0)) 
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ *ns.x + ns.yyyy;
  vec4 y = y_ *ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy,h.x);
  vec3 p1 = vec3(a0.zw,h.y);
  vec3 p2 = vec3(a1.xy,h.z);
  vec3 p3 = vec3(a1.zw,h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(vViewPosition);
    
    // Fresnel calculations
    float fresnel = max(0.0, 1.0 - dot(n, v));
    float fresnelPow = pow(fresnel, 3.0);
    float fresnelGlow = pow(fresnel, 1.5);
    
    // Physical Refraction Vector for seeing "inside" the liquid
    vec3 refRay = refract(-v, n, 1.0 / 1.45);
    
    // Sample the internal volume using 3D noise along the refracted ray
    vec3 samplePos = vWorldPosition + refRay * 1.5;
    float internalNoise1 = snoise(samplePos * 1.2 + uTime * 0.4);
    float internalNoise2 = snoise(samplePos * 2.5 - uTime * 0.6);
    float fluidMix = smoothstep(-1.0, 1.0, internalNoise1 + internalNoise2 * 0.5 + vNoise * 2.0);
    
    // Core Brand Colors (Dark Matter + Neon Plasma)
    vec3 colDark = vec3(0.02, 0.01, 0.04);   // Obsidian / Deep Space Purple
    vec3 colBurgundy = vec3(0.5, 0.0, 0.2);  // Brand Burgundy
    vec3 colOrange = vec3(1.0, 0.4, 0.0);    // Brand Orange (Glowing)
    vec3 colCyan = vec3(0.0, 0.9, 1.0);      // High-energy Electric Cyan
    
    // Mix the internal fluid colors based on the chaotic noise
    vec3 fluidColor = mix(colDark, colBurgundy, smoothstep(0.0, 0.4, fluidMix));
    fluidColor = mix(fluidColor, colOrange, smoothstep(0.4, 0.7, fluidMix));
    fluidColor = mix(fluidColor, colCyan, smoothstep(0.7, 1.0, fluidMix));
    
    // Edge Holographic Rim (Iridescent Oil Slick Effect)
    float iridescencePhase = dot(v, n) * 6.0 + uTime * 0.5 + vNoise * 3.0;
    vec3 iridescence = vec3(
        0.5 + 0.5 * cos(iridescencePhase + 0.0),
        0.5 + 0.5 * cos(iridescencePhase + 2.0),
        0.5 + 0.5 * cos(iridescencePhase + 4.0)
    );
    
    // Combine internal glowing fluid with the holographic surface
    // The surface becomes completely iridescent at grazing angles
    vec3 finalColor = mix(fluidColor, iridescence, fresnelPow * 0.8);
    
    // Intense Cinematic Lighting
    vec3 light1 = normalize(vec3(1.0, 2.0, 1.5));
    vec3 light2 = normalize(vec3(-2.0, -1.0, -0.5));
    
    // Sharp Blinn-Phong Specular for that "wet glossy" look
    vec3 half1 = normalize(light1 + v);
    vec3 half2 = normalize(light2 + v);
    
    float spec1 = pow(max(dot(n, half1), 0.0), 128.0) * 2.0;
    float spec2 = pow(max(dot(n, half2), 0.0), 64.0) * 1.5;
    
    // Add the specular light hits (Warm Key + Cool Fill)
    finalColor += vec3(1.0, 0.8, 0.6) * spec1;
    finalColor += vec3(0.3, 0.7, 1.0) * spec2;
    
    // Add a highly saturated electric rim light
    finalColor += colCyan * fresnelGlow * 0.3;
    
    gl_FragColor = vec4(finalColor, 1.0);
}
`;

const GlassObject = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  
  // Springy magnetic cursor interaction
  const mouseX = useSpring(0, { stiffness: 60, damping: 15 });
  const mouseY = useSpring(0, { stiffness: 60, damping: 15 });
  
  const { viewport } = useThree();

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -(e.clientY / window.innerHeight) * 2 + 1;
      mouseX.set(x);
      mouseY.set(y);
    };
    
    const handleMouseLeave = () => {
      mouseX.set(0);
      mouseY.set(0);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);
    
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [mouseX, mouseY]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uResolution: { value: new THREE.Vector2() },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uMagneticStrength: { value: 0.0 },
    }),
    []
  );

  useFrame((state) => {
    if (materialRef.current) {
      const u = materialRef.current.uniforms;
      if (u && u.uTime && u.uResolution && u.uMouse && u.uMagneticStrength) {
        // Fast time for dynamic liquid look
        u.uTime.value = state.clock.elapsedTime;
        u.uResolution.value.set(
          window.innerWidth * window.devicePixelRatio,
          window.innerHeight * window.devicePixelRatio
        );
        u.uMouse.value.set(mouseX.get(), mouseY.get());
        
        const distToCenter = Math.sqrt(mouseX.get() ** 2 + mouseY.get() ** 2);
        u.uMagneticStrength.value = THREE.MathUtils.lerp(
          u.uMagneticStrength.value,
          distToCenter > 0.05 ? 1.0 : 0.0,
          0.1
        );
      }
    }
    
    if (meshRef.current) {
      // Natural drifting rotation
      meshRef.current.rotation.y += 0.001;
      meshRef.current.rotation.x += 0.001;
    }
  });

  return (
    <mesh ref={meshRef}>
      {/* High polygon count for complex liquid vertex morphing */}
      <sphereGeometry args={[1.5, 128, 128]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
};

export default function RefractiveGlassBackground() {
  return (
    <div 
      className="absolute inset-0 w-full h-full z-0 overflow-hidden pointer-events-none"
      style={{ background: "radial-gradient(circle at center, #0a0510 0%, #000000 100%)" }}
    >
      <Canvas
        camera={{ position: [0, 0, 5], fov: 45 }}
        dpr={typeof window !== "undefined" ? Math.min(window.devicePixelRatio, 2) : 1}
        gl={{ 
            antialias: true, 
            alpha: true,
            powerPreference: "high-performance"
        }}
      >
        <GlassObject />
      </Canvas>
    </div>
  );
}
