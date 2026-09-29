import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { RiskLevel } from "../../types/prediction";

interface AtmosphericSceneProps {
  map: MapLibreMap | null;
  latitude: number | null;
  longitude: number | null;
  riskLevel: RiskLevel | null;
  probability: number;
}

const COLORS: Record<RiskLevel, number> = {
  LOW: 0x4ccf8a,
  MODERATE: 0xe2b23b,
  HIGH: 0xf07a4f,
  SEVERE: 0xe34e55,
};

export default function AtmosphericScene({
  map, latitude, longitude, riskLevel, probability,
}: AtmosphericSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef({ map, latitude, longitude, riskLevel, probability });
  stateRef.current = { map, latitude, longitude, riskLevel, probability };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(0, host.clientWidth, 0, host.clientHeight, -100, 100);

    const group = new THREE.Group();
    scene.add(group);

    const ringGroup = new THREE.Group();
    group.add(ringGroup);

    const rings: THREE.Mesh[] = [];
    [18, 34, 54].forEach((radius, index) => {
      const geometry = new THREE.RingGeometry(radius - 0.65, radius + 0.65, 96);
      const material = new THREE.MeshBasicMaterial({
        color: 0x7dd3fc,
        transparent: true,
        opacity: 0.16 - index * 0.035,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(geometry, material);
      rings.push(mesh);
      ringGroup.add(mesh);
    });

    const beamGeometry = new THREE.CylinderGeometry(1.2, 4.2, 95, 24, 1, true);
    const beamMaterial = new THREE.MeshBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.12,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const beam = new THREE.Mesh(beamGeometry, beamMaterial);
    beam.rotation.z = Math.PI / 2;
    group.add(beam);

    const coreGeometry = new THREE.CircleGeometry(4.5, 32);
    const coreMaterial = new THREE.MeshBasicMaterial({
      color: 0xdff8ff,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    });
    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    group.add(core);

    const particleCount = 180;
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 260;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 160;
      positions[i * 3 + 2] = 0;
      velocities[i] = 0.12 + Math.random() * 0.28;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x9adcf5,
      size: 1.3,
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    const resize = () => {
      if (!host) return;
      renderer.setSize(host.clientWidth, host.clientHeight);
      camera.right = host.clientWidth;
      camera.bottom = host.clientHeight;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const s = stateRef.current;
      const w = host.clientWidth;
      const h = host.clientHeight;

      let x = w / 2;
      let y = h / 2;
      if (s.map && s.latitude !== null && s.longitude !== null) {
        const point = s.map.project([s.longitude, s.latitude]);
        x = point.x;
        y = point.y;
      }
      group.position.set(x, y, 0);
      ringGroup.rotation.z += 0.0025;
      rings.forEach((ring, i) => {
        const pulse = 1 + Math.sin(performance.now() * 0.0012 + i) * 0.045;
        ring.scale.setScalar(pulse);
      });

      const color = s.riskLevel ? COLORS[s.riskLevel] : 0x7dd3fc;
      (coreMaterial.color as THREE.Color).setHex(color);
      (beamMaterial.color as THREE.Color).setHex(color);
      rings.forEach(r => (r.material as THREE.MeshBasicMaterial).color.setHex(color));
      const intensity = 0.15 + Math.min(s.probability, 100) / 100 * 0.5;
      coreMaterial.opacity = Math.min(1, intensity + 0.45);
      beamMaterial.opacity = 0.06 + intensity * 0.12;

      const arr = particleGeometry.attributes.position.array as Float32Array;
      for (let i = 0; i < particleCount; i += 1) {
        const idx = i * 3;
        arr[idx] += velocities[i];
        if (arr[idx] > 140) arr[idx] = -140;
      }
      particleGeometry.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    };
    animate();

    const onMapMove = () => {};
    map?.on("move", onMapMove);

    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      map?.off("move", onMapMove);
      particleGeometry.dispose();
      particleMaterial.dispose();
      beamGeometry.dispose();
      beamMaterial.dispose();
      coreGeometry.dispose();
      coreMaterial.dispose();
      rings.forEach(r => { r.geometry.dispose(); (r.material as THREE.Material).dispose(); });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [map]);

  return <div ref={hostRef} className="atmosphere-canvas" aria-hidden="true" />;
}
