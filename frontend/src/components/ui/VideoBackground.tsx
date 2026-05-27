type Props = {
  src: string;
  poster?: string;
  className?: string;
  overlayClassName?: string;
};

export function VideoBackground({ src, poster, className = "", overlayClassName = "" }: Props) {
  return (
    <div className={`absolute inset-0 -z-10 overflow-hidden ${className}`}>
      <video
        autoPlay
        muted
        loop
        playsInline
        poster={poster}
        className="h-full w-full object-cover"
      >
        <source src={src} type="video/mp4" />
      </video>
      <div className={`absolute inset-0 bg-background/60 ${overlayClassName}`} />
    </div>
  );
}
