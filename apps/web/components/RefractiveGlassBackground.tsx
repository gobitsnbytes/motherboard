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
  
  // Base organic breathing
  float noise = snoise(position * 1.5 + uTime * 0.2);
  vec3 displacedPosition = position + normal * noise * 0.15;
  
  // Magnetic cursor physics
  // uMouse is mapped to rough world coordinates at z=0
  vec3 mouseWorld = vec3(uMouse.x * 5.0, uMouse.y * 5.0, 0.0);
  float dist = distance(displacedPosition, mouseWorld);
  float influence = exp(-dist * dist * 0.5) * uMagneticStrength;
  
  // Bend vertices towards or away from mouse slightly
  vec3 dir = normalize(displacedPosition - mouseWorld);
  displacedPosition += dir * influence * 0.3;
  
  vec4 modelPosition = modelMatrix * vec4(displacedPosition, 1.0);
  vec4 mvPosition = viewMatrix * modelPosition;
  
  // Recalculate normal approximation (simplistic approach for performance)
  vNormal = normalize(normalMatrix * normal + dir * influence * 0.5);
  
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

// Simple hash for procedural stars
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

// Procedural background matching the CSS background
vec3 getBackground(vec2 uv) {
    // Warm gray to black gradient
    vec2 center = vec2(0.5);
    float dist = distance(uv, center);
    vec3 color = mix(vec3(0.07, 0.06, 0.05), vec3(0.0), smoothstep(0.0, 0.8, dist));
    
    // Sparse stars
    float star = hash(uv * uResolution);
    if(star > 0.998) {
        float brightness = (star - 0.998) * 500.0;
        float flicker = sin(uTime * 3.0 + star * 100.0) * 0.5 + 0.5;
        color += vec3(1.0, 0.9, 0.8) * brightness * flicker;
    }
    
    // Vignette
    color *= 1.0 - smoothstep(0.5, 1.5, dist);
    
    return color;
}

// Cosine palette for thin film interference
vec3 palette( in float t, in vec3 a, in vec3 b, in vec3 c, in vec3 d ) {
    return a + b*cos( 6.28318*(c*t+d) );
}

void main() {
    vec3 normal = normalize(vNormal);
    vec3 viewDir = normalize(vViewPosition);
    
    // Fresnel factor
    float fresnel = dot(viewDir, normal);
    fresnel = clamp(1.0 - fresnel, 0.0, 1.0);
    float fresnelPow = pow(fresnel, 3.0);
    
    // Screen-space UV for refraction
    vec2 screenUv = gl_FragCoord.xy / uResolution.xy;
    
    // Chromatic dispersion offsets
    float distortion = 0.15 * fresnel;
    vec2 refR = screenUv - normal.xy * distortion * 1.0;
    vec2 refG = screenUv - normal.xy * distortion * 1.05;
    vec2 refB = screenUv - normal.xy * distortion * 1.1;
    
    vec3 bgColor;
    bgColor.r = getBackground(refR).r;
    bgColor.g = getBackground(refG).g;
    bgColor.b = getBackground(refB).b;
    
    // Thin Film Interference (Iridescence)
    // Shift colors based on view angle and normal to simulate dielectric layer
    float filmThickness = vWorldPosition.y * 0.1 + uTime * 0.05 + fresnel;
    vec3 iridescence = palette(
        filmThickness, 
        vec3(0.5, 0.5, 0.5),      // a
        vec3(0.5, 0.5, 0.5),      // b
        vec3(1.0, 1.0, 1.0),      // c
        vec3(0.0, 0.33, 0.67)     // d (shifts towards gold/blue/violet)
    );
    
    // Only apply iridescence aggressively on the edges (high fresnel)
    iridescence *= smoothstep(0.4, 1.0, fresnelPow) * 1.5;
    
    // Internal reflection / soft caustic glow in the center
    float internalCaustic = pow(max(0.0, dot(viewDir, normal)), 4.0) * 0.1;
    vec3 causticColor = vec3(1.0, 0.9, 0.8) * internalCaustic;
    
    // Lighting
    // Warm key light
    vec3 lightDir1 = normalize(vec3(1.0, 1.0, 1.0));
    float diff1 = max(0.0, dot(normal, lightDir1));
    vec3 spec1 = vec3(1.0, 0.8, 0.6) * pow(max(0.0, dot(reflect(-lightDir1, normal), viewDir)), 32.0);
    
    // Cool rim light
    vec3 lightDir2 = normalize(vec3(-1.0, -1.0, -1.0));
    float diff2 = max(0.0, dot(normal, lightDir2));
    vec3 spec2 = vec3(0.4, 0.6, 1.0) * pow(max(0.0, dot(reflect(-lightDir2, normal), viewDir)), 32.0);
    
    // Combine everything
    vec3 finalColor = bgColor;
    finalColor += iridescence * 0.4; // Subtle thin film
    finalColor += causticColor; // Subtle internal bounce
    finalColor += (spec1 + spec2) * fresnel; // Specular highlights driven by fresnel
    
    // Edge brightening
    finalColor += vec3(0.1, 0.1, 0.1) * fresnelPow;
    
    gl_FragColor = vec4(finalColor, 1.0);
}
`;

const GlassObject = () => {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  
  // Critically damped spring for mouse tracking
  const mouseX = useSpring(0, { stiffness: 50, damping: 20 });
  const mouseY = useSpring(0, { stiffness: 50, damping: 20 });
  
  const { viewport } = useThree();

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      // Normalize mouse to -1 to +1
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -(e.clientY / window.innerHeight) * 2 + 1;
      mouseX.set(x);
      mouseY.set(y);
    };
    
    const handleMouseLeave = () => {
      // Return to center when mouse leaves
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
      uMagneticStrength: { value: 1.0 },
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
        u.uMouse.value.set(
          mouseX.get(),
          mouseY.get()
        );
        
        // Calculate cursor velocity/distance for dynamic magnetic strength
        const distToCenter = Math.sqrt(mouseX.get() ** 2 + mouseY.get() ** 2);
        u.uMagneticStrength.value = THREE.MathUtils.lerp(
          u.uMagneticStrength.value,
          distToCenter > 0.05 ? 1.5 : 0.0,
          0.1
        );
      }
    }
    
    if (meshRef.current) {
      // Extremely slow natural rotation
      meshRef.current.rotation.y += 0.001;
      meshRef.current.rotation.x += 0.0005;
    }
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1.5, 8]} />
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
      style={{
        // Matching the CSS background mathematically to the shader's getBackground
        background: "radial-gradient(circle at center, #120f0c 0%, #000000 80%)"
      }}
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
