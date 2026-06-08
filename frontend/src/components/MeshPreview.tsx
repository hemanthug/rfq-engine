import { RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { PreviewMeshResult, WarningMarker } from "../types";
import { LoadingSteps } from "./LoadingSteps";

type HoverState = { marker: WarningMarker; x: number; y: number };

const PREVIEW_STEPS = [
  "Reading STEP file",
  "Parsing solid geometry",
  "Extracting features",
  "Tessellating mesh",
  "Preparing preview",
];

type MeshPreviewProps = {
  preview: PreviewMeshResult | null;
  isLoading: boolean;
  markers?: WarningMarker[];
  onNewQuote?: () => void;
};

const MARKER_COLOR = 0xf59e0b;

function makeWarningSprite(label: string) {
  const dimension = 128;
  const canvas = document.createElement("canvas");
  canvas.width = dimension;
  canvas.height = dimension;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, dimension, dimension);
    ctx.beginPath();
    ctx.arc(dimension / 2, dimension / 2, dimension * 0.4, 0, Math.PI * 2);
    ctx.fillStyle = "#f59e0b";
    ctx.fill();
    ctx.lineWidth = dimension * 0.07;
    ctx.strokeStyle = "#7c2d12";
    ctx.stroke();
    ctx.fillStyle = "#1f1300";
    ctx.font = `bold ${dimension * 0.5}px "IBM Plex Sans", system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, dimension / 2, dimension / 2 + dimension * 0.02);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 4;
  const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, depthWrite: false, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.renderOrder = 30;
  return sprite;
}

export function MeshPreview({ preview, isLoading, markers = [], onNewQuote }: MeshPreviewProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !preview) {
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f6f4);

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
      color: 0x6f8a87,
      metalness: 0.2,
      roughness: 0.45,
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

    const diagonal = size.length();
    const markerGroup = new THREE.Group();
    const spriteScale = Math.max(diagonal * 0.05, 0.5);
    for (const marker of markers) {
      const origin = new THREE.Vector3(marker.position[0], marker.position[1], marker.position[2]);

      if (marker.radius && marker.direction) {
        const tube = Math.max(marker.radius * 0.09, diagonal * 0.0035);
        const ringGeometry = new THREE.TorusGeometry(marker.radius, tube, 12, 48);
        const ringMaterial = new THREE.MeshBasicMaterial({
          color: MARKER_COLOR,
          depthTest: false,
          transparent: true,
          opacity: 0.95,
        });
        const ring = new THREE.Mesh(ringGeometry, ringMaterial);
        ring.renderOrder = 25;
        ring.userData.marker = marker;
        const direction = new THREE.Vector3(marker.direction[0], marker.direction[1], marker.direction[2]).normalize();
        ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), direction);
        ring.position.copy(origin);
        markerGroup.add(ring);
      } else {
        const dotGeometry = new THREE.SphereGeometry(Math.max(diagonal * 0.012, 0.3), 16, 16);
        const dotMaterial = new THREE.MeshBasicMaterial({ color: MARKER_COLOR, depthTest: false, transparent: true });
        const dot = new THREE.Mesh(dotGeometry, dotMaterial);
        dot.renderOrder = 25;
        dot.userData.marker = marker;
        dot.position.copy(origin);
        markerGroup.add(dot);
      }

      const sprite = makeWarningSprite(String(marker.number));
      sprite.position.copy(origin);
      sprite.scale.set(spriteScale, spriteScale, spriteScale);
      sprite.userData.marker = marker;
      markerGroup.add(sprite);
    }
    scene.add(markerGroup);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const findMarker = (object: THREE.Object3D | null): WarningMarker | null => {
      let current: THREE.Object3D | null = object;
      while (current) {
        const candidate = current.userData?.marker as WarningMarker | undefined;
        if (candidate) {
          return candidate;
        }
        current = current.parent;
      }
      return null;
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (markers.length === 0) {
        return;
      }
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const intersections = raycaster.intersectObjects(markerGroup.children, true);
      const marker = intersections.length > 0 ? findMarker(intersections[0].object) : null;
      renderer.domElement.style.cursor = marker ? "pointer" : "";
      setHover(marker ? { marker, x: event.clientX - rect.left, y: event.clientY - rect.top } : null);
    };

    const handlePointerLeave = () => {
      renderer.domElement.style.cursor = "";
      setHover(null);
    };

    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerleave", handlePointerLeave);

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
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerleave", handlePointerLeave);
      setHover(null);
      controls.dispose();
      geometry.dispose();
      material.dispose();
      markerGroup.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();
        const objectMaterial = (object as THREE.Mesh | THREE.Sprite).material as THREE.Material | undefined;
        if (objectMaterial) {
          const map = (objectMaterial as THREE.SpriteMaterial).map;
          map?.dispose();
          objectMaterial.dispose();
        }
      });
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [preview, markers]);

  return (
    <section className="preview-panel" aria-label="STEP preview">
      <div className="preview-toolbar">
        <div>
          <h2>STEP Preview</h2>
          <span>{preview ? `${preview.triangle_count.toLocaleString()} triangles` : "Waiting for upload"}</span>
        </div>
        <div className="preview-toolbar-actions">
          {preview && <span className="unit-pill">{preview.units}</span>}
          {onNewQuote && (
            <button type="button" className="preview-action" onClick={onNewQuote}>
              <RotateCcw size={14} />
              New quote
            </button>
          )}
        </div>
      </div>
      <div className="viewport" ref={mountRef}>
        {!preview && isLoading && (
          <div className="viewport-empty viewport-empty-loading">
            <LoadingSteps title="Generating preview" steps={PREVIEW_STEPS} />
          </div>
        )}
        {!preview && !isLoading && (
          <div className="viewport-empty">
            <strong>No CAD loaded</strong>
            <span>Upload a STEP or STP file to render the preview.</span>
          </div>
        )}
        {preview && markers.length > 0 && (
          <div className="warning-hint" aria-label="Geometry warnings on model">
            <span className="warning-pin warning-pin-sm">!</span>
            <span>
              {markers.length} geometry {markers.length === 1 ? "warning" : "warnings"} · hover a marker
            </span>
          </div>
        )}
        {hover && (
          <div className="warning-tooltip" style={{ left: hover.x, top: hover.y }} role="tooltip">
            <span className="warning-tooltip-head">
              <span className="warning-pin warning-pin-sm">{hover.marker.number}</span>
              {hover.marker.faceId}
            </span>
            <ul>
              {hover.marker.warnings.map((warning) => (
                <li key={warning}>{warning.replace(/_/g, " ")}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
