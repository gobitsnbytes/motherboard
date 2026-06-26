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

// Procedural 3D Noise for organic breathing
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
  vUv = uv;
  
  // Extremely slow, subtle organic breathing (reduced amplitude)
  float noise = snoise(position * 1.2 + uTime * 0.1);
  vec3 displacedPosition = position + normal * noise * 0.06;
  
  // Magnetic cursor physics mapping
  vec3 mouseWorld = vec3(uMouse.x * 4.0, uMouse.y * 4.0, 0.0);
  float dist = distance(displacedPosition, mouseWorld);
  float influence = exp(-dist * dist * 0.8) * uMagneticStrength;
  
  // Subtle pull towards cursor
  vec3 dir = normalize(displacedPosition - mouseWorld);
  displacedPosition += dir * influence * 0.15;
  
  vec4 modelPosition = modelMatrix * vec4(displacedPosition, 1.0);
  vec4 mvPosition = viewMatrix * modelPosition;
  
  // Basic normal recalculation
  vNormal = normalize(normalMatrix * normal + dir * influence * 0.3);
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

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// Faked "Environment Map" for the glass to refract. 
// Adding invisible softboxes to the mathematical space gives the glass
// high-contrast edges to bend, making it look incredibly realistic.
vec3 getEnvironment(vec2 uv) {
    vec2 center = vec2(0.5);
    float dist = distance(uv, center);
    
    // Deep warm gray base
    vec3 color = mix(vec3(0.06, 0.05, 0.04), vec3(0.0), smoothstep(0.0, 0.9, dist));
    
    // Faked Softbox Light 1 (Warm, Top Right)
    float light1 = smoothstep(0.3, 0.0, length(vec2(uv.x - 0.7, (uv.y - 0.8) * 1.5)));
    color += vec3(0.15, 0.1, 0.05) * light1;
    
    // Faked Softbox Light 2 (Cool, Bottom Left)
    float light2 = smoothstep(0.4, 0.0, length(vec2((uv.x - 0.2) * 2.0, uv.y - 0.2)));
    color += vec3(0.02, 0.05, 0.1) * light2;
    
    // Procedural Stars
    float star = hash(uv * uResolution);
    if(star > 0.999) {
        float brightness = (star - 0.999) * 800.0;
        float flicker = sin(uTime * 2.0 + star * 100.0) * 0.5 + 0.5;
        color += vec3(1.0, 0.9, 0.8) * brightness * flicker;
    }
    
    return color;
}

void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(vViewPosition);
    
    // Schlick's approximation for Fresnel
    float f0 = 0.04;
    float fresnel = f0 + (1.0 - f0) * pow(1.0 - max(dot(n, v), 0.0), 5.0);
    
    // Base Screen UV
    vec2 screenUv = gl_FragCoord.xy / uResolution.xy;
    
    // Physical Refraction using IOR (Borosilicate ~ 1.47)
    // We refract the view vector through the normal
    float iorR = 1.0 / 1.45;
    float iorG = 1.0 / 1.47;
    float iorB = 1.0 / 1.49;
    
    vec3 refRayR = refract(-v, n, iorR);
    vec3 refRayG = refract(-v, n, iorG);
    vec3 refRayB = refract(-v, n, iorB);
    
    float thickness = 0.2; // Apparent thickness mapping
    
    vec2 uvR = screenUv + refRayR.xy * thickness;
    vec2 uvG = screenUv + refRayG.xy * thickness;
    vec2 uvB = screenUv + refRayB.xy * thickness;
    
    vec3 refractionColor;
    refractionColor.r = getEnvironment(uvR).r;
    refractionColor.g = getEnvironment(uvG).g;
    refractionColor.b = getEnvironment(uvB).b;
    
    // Internal Reflection Bounce
    vec3 internalRay = reflect(-v, n);
    vec3 internalColor = getEnvironment(screenUv + internalRay.xy * 0.4) * 0.25;
    
    // Subtle Thin-Film Interference (Dielectric Iridescence)
    float filmPhase = dot(v, n) * 4.0 + vWorldPosition.y * 0.5 + uTime * 0.1;
    vec3 filmColor = vec3(
        0.5 + 0.4 * cos(filmPhase + 0.0),
        0.5 + 0.4 * cos(filmPhase + 2.0),
        0.5 + 0.4 * cos(filmPhase + 4.0)
    );
    // Desaturate to keep it premium and subtle (no neon)
    filmColor = mix(vec3(dot(filmColor, vec3(0.33))), filmColor, 0.25);
    
    // High-end Cinematic Specular Lighting
    vec3 lightDir1 = normalize(vec3(1.0, 1.5, 1.0)); // Warm key
    vec3 lightDir2 = normalize(vec3(-1.0, -1.0, 0.5)); // Cool fill
    
    vec3 half1 = normalize(lightDir1 + v);
    vec3 half2 = normalize(lightDir2 + v);
    
    float spec1 = pow(max(dot(n, half1), 0.0), 128.0) * 1.5;
    float spec2 = pow(max(dot(n, half2), 0.0), 64.0) * 0.5;
    
    vec3 specular = vec3(1.0, 0.9, 0.8) * spec1 + vec3(0.7, 0.8, 1.0) * spec2;
    
    // Composite
    vec3 finalColor = refractionColor + internalColor;
    
    // Add iridescent film strictly to grazing angles
    finalColor += filmColor * fresnel * 0.6;
    
    // Add crisp specular highlights
    finalColor += specular;
    
    gl_FragColor = vec4(finalColor, 1.0);
}
`;

const GlassObject = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  
  // Critically damped spring for premium, heavy feel
  const mouseX = useSpring(0, { stiffness: 40, damping: 25 });
  const mouseY = useSpring(0, { stiffness: 40, damping: 25 });
  
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
          0.05
        );
      }
    }
    
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.0005;
      meshRef.current.rotation.x += 0.0002;
    }
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1.5, 6]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
        depthWrite={false}
      />
    </mesh>
  );
};

export default function RefractiveGlassBackground() {
  return (
    <div 
      className="absolute inset-0 w-full h-full z-0 overflow-hidden pointer-events-none"
      style={{ background: "radial-gradient(circle at center, #120f0c 0%, #000000 80%)" }}
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
