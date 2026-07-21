import { Children } from "react";

export function OrbitingCircles({
  className = "",
  children,
  reverse = false,
  duration = 20,
  delay = 10,
  radius = 160,
  path = true,
  iconSize = 30,
  speed = 1,
}) {
  const childArray = Children.toArray(children);
  const calculatedDuration = duration / speed;

  return (
    <>
      {path && (
        <svg className="orbiting-circles-path" aria-hidden="true">
          <circle cx="50%" cy="50%" r={radius} />
        </svg>
      )}
      {childArray.map((child, index) => {
        const angle = (360 / childArray.length) * index;

        return (
          <div
            className={`orbiting-circles-item ${reverse ? "is-reverse" : ""} ${className}`}
            style={{
              "--duration": `${calculatedDuration}s`,
              "--delay": `${delay}s`,
              "--radius": `${radius}px`,
              "--angle": `${angle}deg`,
              "--angle-negative": `${angle * -1}deg`,
              "--icon-size": `${iconSize}px`,
            }}
            key={index}
          >
            {child}
          </div>
        );
      })}
    </>
  );
}
