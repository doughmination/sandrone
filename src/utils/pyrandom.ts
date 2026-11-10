/* src/utils/pyrandom.ts
 * Sandbina Open Source Licence 1.0 — (c) Clove Twilight
 */

// MT19937, seeded and drawn from exactly like CPython's random.Random
const stateSize = 624
const shiftSize = 397
const matrixA = 0x9908B0DF
const upperMask = 0x80000000
const lowerMask = 0x7FFFFFFF

export class PyRandom {
  private state = new Uint32Array(stateSize)
  private index = stateSize + 1

  constructor(seed: bigint | number | string) {
    this.seedWithInteger(BigInt(seed))
  }

  // An int seed is split into 32-bit words, least significant first
  private seedWithInteger(seed: bigint): void {
    let remaining = seed < 0n ? -seed : seed
    const words: number[] = []
    while (remaining > 0n) {
      words.push(Number(remaining & 0xFFFFFFFFn))
      remaining >>= 32n
    }
    if (words.length === 0) {
      words.push(0)
    }
    this.initByArray(words)
  }

  private initGenrand(seed: number): void {
    const state = this.state
    state[0] = seed >>> 0
    for (let position = 1; position < stateSize; position++) {
      const previous = state[position - 1] ^ (state[position - 1] >>> 30)
      state[position] = (Math.imul(1812433253, previous) + position) >>> 0
    }
    this.index = stateSize
  }

  private initByArray(key: number[]): void {
    const state = this.state
    this.initGenrand(19650218)

    let position = 1
    let keyIndex = 0
    let steps = Math.max(stateSize, key.length)
    for (; steps > 0; steps--) {
      const previous = state[position - 1] ^ (state[position - 1] >>> 30)
      state[position] = ((state[position] ^ Math.imul(previous, 1664525)) +
        key[keyIndex] + keyIndex) >>> 0
      position++
      keyIndex++
      if (position >= stateSize) {
        state[0] = state[stateSize - 1]
        position = 1
      }
      if (keyIndex >= key.length) {
        keyIndex = 0
      }
    }

    for (steps = stateSize - 1; steps > 0; steps--) {
      const previous = state[position - 1] ^ (state[position - 1] >>> 30)
      state[position] =
        ((state[position] ^ Math.imul(previous, 1566083941)) -
          position) >>> 0
      position++
      if (position >= stateSize) {
        state[0] = state[stateSize - 1]
        position = 1
      }
    }

    state[0] = 0x80000000
  }

  private twist(): void {
    const state = this.state
    for (let position = 0; position < stateSize; position++) {
      const mixed = (state[position] & upperMask) |
        (state[(position + 1) % stateSize] & lowerMask)
      let next = state[(position + shiftSize) % stateSize] ^ (mixed >>> 1)
      if (mixed & 1) {
        next ^= matrixA
      }
      state[position] = next >>> 0
    }
    this.index = 0
  }

  nextUint32(): number {
    if (this.index >= stateSize) {
      this.twist()
    }
    let value = this.state[this.index++]
    value ^= value >>> 11
    value ^= (value << 7) & 0x9D2C5680
    value ^= (value << 15) & 0xEFC60000
    value ^= value >>> 18
    return value >>> 0
  }

  // Only up to 32 bits is needed for any list Sandrone picks from
  getRandBits(bits: number): number {
    if (bits <= 0 || bits > 32) {
      throw new RangeError("getRandBits supports 1 to 32 bits")
    }
    return this.nextUint32() >>> (32 - bits)
  }

  // CPython's _randbelow_with_getrandbits
  randBelow(limit: number): number {
    if (limit <= 0) {
      return 0
    }
    const bits = Math.floor(Math.log2(limit)) + 1
    let value = this.getRandBits(bits)
    while (value >= limit) {
      value = this.getRandBits(bits)
    }
    return value
  }

  choice<T>(items: readonly T[]): T {
    if (items.length === 0) {
      throw new RangeError("Cannot choose from an empty sequence")
    }
    return items[this.randBelow(items.length)]
  }
}
