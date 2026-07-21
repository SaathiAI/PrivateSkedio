export function mulberry32(seed: number) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let result = value;
    result = Math.imul(result ^ (result >>> 15), result | 1);
    result ^= result + Math.imul(result ^ (result >>> 7), result | 61);
    return ((result ^ (result >>> 14)) >>> 0) / 4_294_967_296;
  };
}

export function randomDirection(random: () => number) {
  const theta = random() * Math.PI * 2;
  const z = random() * 2 - 1;
  const radius = Math.sqrt(1 - z * z);
  return [radius * Math.cos(theta), radius * Math.sin(theta), z] as const;
}
