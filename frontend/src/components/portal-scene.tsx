import { Mountain } from "lucide-react";

export function DamavandBrand() {
  return (
    <div className="damavand-brand">
      <Mountain size={32} strokeWidth={1.4} />
      <span>
        دماوند<small>DAMAVAND</small>
      </span>
    </div>
  );
}

export function MountainScene() {
  return (
    <div className="mountain-scene" aria-hidden="true">
      <div className="aurora aurora-one" />
      <div className="aurora aurora-two" />
      <div className="scene-stars" />
      <div className="scene-orbit" />
      <svg
        className="mountain-landscape"
        viewBox="0 0 1440 950"
        preserveAspectRatio="xMidYMax slice"
      >
        <defs>
          <linearGradient id="ridge-back" x1="0" y1="0" x2=".4" y2="1">
            <stop stopColor="#655a9e" />
            <stop offset="1" stopColor="#141831" />
          </linearGradient>
          <linearGradient id="ridge-front" x1="0" y1="0" x2="0" y2="1">
            <stop stopColor="#222b49" />
            <stop offset="1" stopColor="#080e20" />
          </linearGradient>
          <linearGradient id="snow" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#e2dff5" />
            <stop offset="1" stopColor="#64769b" />
          </linearGradient>
        </defs>
        <path
          d="M0 750 140 578 250 641 360 464 450 529 670 214 875 507 1010 444 1140 602 1290 526 1440 720V950H0Z"
          fill="url(#ridge-back)"
        />
        <path
          d="m670 214-128 184 61-27 34 36 33-83 45 88 26-28 57 15Z"
          fill="url(#snow)"
        />
        <path
          d="m670 214 14 168 61 67 49 151 81-93Z"
          fill="#b1a6d9"
          opacity=".14"
        />
        <path
          d="M0 950V755l169-96 185 150 153-259 121 136 155-81 170 233 134-115 173 116 180-136V950Z"
          fill="url(#ridge-front)"
        />
        <path
          d="m354 809 153-259-68 248 67-57 122-55-51 96-71-26-23 112Z"
          fill="#646c94"
          opacity=".2"
        />
        <path d="m783 605 94 180 76 53-115-211Z" fill="#848bc4" opacity=".16" />
        <path d="M0 917q355-94 672-11t768-36v80H0Z" fill="#080e20" />
      </svg>
      <div className="scene-haze" />
    </div>
  );
}
