import { RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { PreviewMeshResult } from "../types";
import { LoadingSteps } from "./LoadingSteps";

const PREVIEW_STEPS = [
  "Reading STEP file",
  "Parsing solid geometry",
  "Extracting features",
  "Tessellating mesh",
  "Preparing preview",
];

type ViewId = "iso" | "front" | "back" | "top" | "bottom" | "left" | "right";

type View = { id: ViewId; label: string; direction: [number, number, number]; up: [number, number, number] };

const VIEWS: View[] = [
  { id: "iso", label: "Iso", direction: [1, 0.7, 1], up: [0, 1, 0] },
  { id: "front", label: "Front", direction: [0, 0, 1], up: [0, 1, 0] },
  { id: "back", label: "Back", direction: [0, 0, -1], up: [0, 1, 0] },
  { id: "top", label: "Top", direction: [0, 1, 0], up: [0, 0, -1] },
  { id: "bottom", label: "Bottom", direction: [0, -1, 0], up: [0, 0, 1] },
  { id: "left", label: "Left", direction: [-1, 0, 0], up: [0, 1, 0] },
  { id: "right", label: "Right", direction: [1, 0, 0], up: [0, 1, 0] },
];

const VIEW_BY_ID = new Map(VIEWS.map((view) => [view.id, view]));

// BoxGeometry material order: +x, -x, +y, -y, +z, -z
const CUBE_FACE_VIEWS: ViewId[] = ["right", "left", "top", "bottom", "front", "back"];

type RenderStyle = "edges" | "xray" | "normals";

const RENDER_STYLES: { id: RenderStyle; label: string }[] = [
  { id: "edges", label: "Edges" },
  { id: "xray", label: "X-ray" },
  { id: "normals", label: "Normals" },
];

function makeMeshMaterial(style: RenderStyle): THREE.Material {
  switch (style) {
    case "xray":
      return new THREE.MeshStandardMaterial({
        color: 0x6f8a87,
        metalness: 0.1,
        roughness: 0.5,
        transparent: true,
        opacity: 0.32,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
    case "normals":
      return new THREE.MeshNormalMaterial({ flatShading: true, side: THREE.DoubleSide });
    case "edges":
    default:
      return new THREE.MeshStandardMaterial({
        color: 0x6f8a87,
        metalness: 0.2,
        roughness: 0.45,
        side: THREE.DoubleSide,
      });
  }
}

function edgesVisibleFor(style: RenderStyle) {
  return style === "edges" || style === "xray";
}

type MeshPreviewProps = {
  preview: PreviewMeshResult | null;
  isLoading: boolean;
  onNewQuote?: () => void;
};

type ViewController = {
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  center: THREE.Vector3;
  radius: number;
};

type SceneRefs = {
  mesh: THREE.Mesh;
  edgeLines: THREE.LineSegments | null;
};

function makeFaceTexture(label: string) {
  const dimension = 128;
  const canvas = document.createElement("canvas");
  canvas.width = dimension;
  canvas.height = dimension;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#f3f6f4";
    ctx.fillRect(0, 0, dimension, dimension);
    ctx.strokeStyle = "#c2ccc8";
    ctx.lineWidth = 6;
    ctx.strokeRect(3, 3, dimension - 6, dimension - 6);
    ctx.fillStyle = "#273239";
    ctx.font = 'bold 20px "IBM Plex Sans", system-ui, sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label.toUpperCase(), dimension / 2, dimension / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 4;
  return texture;
}

export function MeshPreview({ preview, isLoading, onNewQuote }: MeshPreviewProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const cubeMountRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<ViewController | null>(null);
  const sceneRef = useRef<SceneRefs | null>(null);
  const [renderStyle, setRenderStyle] = useState<RenderStyle>("edges");
  const renderStyleRef = useRef(renderStyle);
  renderStyleRef.current = renderStyle;

  const applyRenderStyle = useCallback((style: RenderStyle) => {
    const refs = sceneRef.current;
    if (!refs) {
      return;
    }
    const previous = refs.mesh.material as THREE.Material;
    const next = makeMeshMaterial(style);
    refs.mesh.material = next;
    if (previous !== next) {
      previous.dispose();
    }
    if (refs.edgeLines) {
      refs.edgeLines.visible = edgesVisibleFor(style);
    }
  }, []);

  const applyOrientation = useCallback((direction: THREE.Vector3, up: THREE.Vector3) => {
    const controller = viewRef.current;
    if (!controller) {
      return;
    }
    const { camera, controls, center, radius } = controller;
    const dir = direction.clone().normalize();
    const distance = radius * 2.2;
    camera.up.copy(up).normalize();
    camera.position.copy(center).addScaledVector(dir, distance);
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
  }, []);

  const applyView = useCallback(
    (view: View) => {
      applyOrientation(new THREE.Vector3(...view.direction), new THREE.Vector3(...view.up));
    },
    [applyOrientation],
  );

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

    const initialStyle = renderStyleRef.current;
    const mesh = new THREE.Mesh(geometry, makeMeshMaterial(initialStyle));
    scene.add(mesh);

    let edgeLines: THREE.LineSegments | null = null;
    let edgeGeometry: THREE.BufferGeometry | null = null;
    let edgeMaterial: THREE.LineBasicMaterial | null = null;
    if (preview.edges.length > 0) {
      edgeGeometry = new THREE.BufferGeometry();
      edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(preview.edges, 3));
      edgeMaterial = new THREE.LineBasicMaterial({ color: 0x273239, transparent: true, opacity: 0.22 });
      edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
      edgeLines.visible = edgesVisibleFor(initialStyle);
      scene.add(edgeLines);
    }

    sceneRef.current = { mesh, edgeLines };

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

    viewRef.current = { camera, controls, center, radius };

    // ---- Orientation view cube (top-right overlay) ----
    const cubeMount = cubeMountRef.current;
    let cubeRenderer: THREE.WebGLRenderer | null = null;
    let cubeScene: THREE.Scene | null = null;
    let cubeCamera: THREE.PerspectiveCamera | null = null;
    let cube: THREE.Mesh | null = null;
    const cubeFaceTextures: THREE.Texture[] = [];
    const cubeRaycaster = new THREE.Raycaster();
    const cubePointer = new THREE.Vector2();

    const handleCubeClick = (event: MouseEvent) => {
      if (!cubeRenderer || !cubeCamera || !cube) {
        return;
      }
      const rect = cubeRenderer.domElement.getBoundingClientRect();
      cubePointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      cubePointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      cubeRaycaster.setFromCamera(cubePointer, cubeCamera);
      const hit = cubeRaycaster.intersectObject(cube)[0];
      if (!hit) {
        return;
      }

      // Where on the 1x1x1 cube the click landed (faces sit at ±0.5).
      // Near an edge/corner a second/third axis crosses the threshold, so we
      // roll toward the adjacent face(s) for a combined angled view.
      const local = cube.worldToLocal(hit.point.clone());
      const edgeZone = 0.35;
      const direction = new THREE.Vector3(
        Math.abs(local.x) > edgeZone ? Math.sign(local.x) : 0,
        Math.abs(local.y) > edgeZone ? Math.sign(local.y) : 0,
        Math.abs(local.z) > edgeZone ? Math.sign(local.z) : 0,
      );
      if (direction.lengthSq() === 0) {
        return;
      }

      const isVertical = direction.x === 0 && direction.z === 0;
      const up = isVertical ? new THREE.Vector3(0, 0, -Math.sign(direction.y)) : new THREE.Vector3(0, 1, 0);
      applyOrientation(direction, up);
    };

    if (cubeMount) {
      const cubeSize = cubeMount.clientWidth || 88;
      cubeRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      cubeRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      cubeRenderer.setSize(cubeSize, cubeSize);
      cubeMount.appendChild(cubeRenderer.domElement);

      cubeScene = new THREE.Scene();
      cubeCamera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);

      const cubeMaterials = CUBE_FACE_VIEWS.map((id) => {
        const texture = makeFaceTexture(VIEW_BY_ID.get(id)!.label);
        cubeFaceTextures.push(texture);
        return new THREE.MeshBasicMaterial({ map: texture });
      });
      cube = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), cubeMaterials);
      cubeScene.add(cube);

      cubeRenderer.domElement.addEventListener("click", handleCubeClick);
    }

    const cubeOffset = new THREE.Vector3();

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);

      if (cubeRenderer && cubeScene && cubeCamera) {
        cubeOffset.subVectors(camera.position, controls.target).normalize().multiplyScalar(2.6);
        cubeCamera.position.copy(cubeOffset);
        cubeCamera.up.copy(camera.up);
        cubeCamera.lookAt(0, 0, 0);
        cubeRenderer.render(cubeScene, cubeCamera);
      }
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
      (mesh.material as THREE.Material).dispose();
      edgeGeometry?.dispose();
      edgeMaterial?.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      viewRef.current = null;
      sceneRef.current = null;

      if (cubeRenderer) {
        cubeRenderer.domElement.removeEventListener("click", handleCubeClick);
        cube?.geometry.dispose();
        cubeFaceTextures.forEach((texture) => texture.dispose());
        (cube?.material as THREE.Material[] | undefined)?.forEach((mat) => mat.dispose());
        cubeRenderer.dispose();
        cubeMount?.removeChild(cubeRenderer.domElement);
      }
    };
  }, [preview, applyOrientation]);

  useEffect(() => {
    applyRenderStyle(renderStyle);
  }, [renderStyle, applyRenderStyle, preview]);

  return (
    <section className="preview-panel" aria-label="STEP preview">
      <div className="preview-toolbar">
        <div>
          <h2>Preview</h2>
        </div>
        <div className="preview-toolbar-actions">
          {onNewQuote && (
            <button type="button" className="preview-action" onClick={onNewQuote}>
              <RotateCcw size={14} />
              New quote
            </button>
          )}
        </div>
      </div>
      <div className="viewport" ref={mountRef}>
        <div
          className="view-cube"
          ref={cubeMountRef}
          aria-label="Orientation cube — click a face to change view"
          style={{ display: preview ? "block" : "none" }}
        />
        {preview && (
          <div className="render-styles" role="group" aria-label="Render style">
            {RENDER_STYLES.map((style) => (
              <button
                key={style.id}
                type="button"
                className={renderStyle === style.id ? "active" : ""}
                onClick={() => setRenderStyle(style.id)}
              >
                {style.label}
              </button>
            ))}
          </div>
        )}
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
      </div>
    </section>
  );
}
