import React from "react";

// Rotrix L-1000: logotipo em texto (o logo do Handy nao e usado: marca propria).
const HandyTextLogo = ({
  width,
  height,
  className,
}: {
  width?: number;
  height?: number;
  className?: string;
}) => {
  return (
    <svg
      width={width}
      height={height}
      className={className}
      viewBox="0 0 930 328"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Rotrix L-1000"
    >
      <text
        x="0"
        y="205"
        className="logo-primary"
        fontFamily="Inter, Segoe UI, Arial, sans-serif"
        fontWeight="800"
        fontSize="230"
        letterSpacing="-6"
      >
        ROTRIX
      </text>
      <text
        x="6"
        y="310"
        className="logo-primary"
        fontFamily="Inter, Segoe UI, Arial, sans-serif"
        fontWeight="600"
        fontSize="92"
        letterSpacing="18"
        opacity="0.75"
      >
        L-1000
      </text>
    </svg>
  );
};

export default HandyTextLogo;
