import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { PreviewMeshResult } from "../types";

type MeshPreviewProps = {
  preview: PreviewMeshResult | null;
  isLoading: boolean;
};

export function MeshPreview({ preview, isLoading }: MeshPreviewProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !preview) {
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf7f8f4);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(38, mount.clientWidth / mount.clientHeight, 0.1, 100000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(preview.positions, 3));
    geometry.setAttribute("normal", new THREE.Float32BufferAttribute(preview.normals, 3));
    geometry.setIndex(preview.indices);
    geometry.computeBoundingSphere();

    const material = new THREE.MeshStandardMaterial({
      color: 0x7c8f96,
      metalness: 0.18,
      roughness: 0.48,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    if (preview.edges.length > 0) {
      const edgeGeometry = new THREE.BufferGeometry();
      edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(preview.edges, 3));
      const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x273239, transparent: true, opacity: 0.22 });
      scene.add(new THREE.LineSegments(edgeGeometry, edgeMaterial));
    }

    const keyLight = new THREE.DirectionalLight(0xffffff, 2.1);
    keyLight.position.set(1.4, 2.4, 2.2);
    scene.add(keyLight);
    scene.add(new THREE.AmbientLight(0xffffff, 1.8));

    const center = new THREE.Vector3(
      (preview.bbox.minimum[0] + preview.bbox.maximum[0]) / 2,
      (preview.bbox.minimum[1] + preview.bbox.maximum[1]) / 2,
      (preview.bbox.minimum[2] + preview.bbox.maximum[2]) / 2,
    );
    const size = new THREE.Vector3(preview.bbox.size[0], preview.bbox.size[1], preview.bbox.size[2]);
    const radius = Math.max(size.length() * 0.6, 1);
    camera.position.set(center.x + radius, center.y + radius * 0.7, center.z + radius);
    camera.near = Math.max(radius / 1000, 0.01);
    camera.far = radius * 100;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const resizeObserver = new ResizeObserver(() => {
      if (!mount.clientWidth || !mount.clientHeight) {
        return;
      }
      renderer.setSize(mount.clientWidth, mount.clientHeight);
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
    });
    resizeObserver.observe(mount);

    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      controls.dispose();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [preview]);

  return (
    <section className="preview-panel" aria-label="STEP preview">
      <div className="preview-toolbar">
        <div>
          <h2>STEP Preview</h2>
          <span>{preview ? `${preview.triangle_count.toLocaleString()} triangles` : "Waiting for upload"}</span>
        </div>
        {preview && <span className="unit-pill">{preview.units}</span>}
      </div>
      <div className="viewport" ref={mountRef}>
        {!preview && (
          <div className="viewport-empty">
            <strong>{isLoading ? "Generating preview" : "No CAD loaded"}</strong>
            <span>{isLoading ? "OpenCascade is tessellating the STEP file." : "Upload a STEP or STP file to render the backend mesh."}</span>
          </div>
        )}
      </div>
    </section>
  );
}
