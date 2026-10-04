import { inr } from '../api'

export interface TreeNode {
  id: number
  name: string
  direct_earnings: number
  earned_for_me: number
  children: TreeNode[]
}

interface Placed {
  node: TreeNode
  x: number
  y: number
  parent?: Placed
}

const NODE_W = 150
const NODE_H = 62
const GAP_X = 26
const GAP_Y = 86

function layout(root: TreeNode): { placed: Placed[]; width: number; height: number } {
  const placed: Placed[] = []
  let nextLeafX = 0
  let maxDepth = 0

  function walk(node: TreeNode, depth: number, parent?: Placed): Placed {
    maxDepth = Math.max(maxDepth, depth)
    const p: Placed = { node, x: 0, y: depth * (NODE_H + GAP_Y), parent }
    if (node.children.length === 0) {
      p.x = nextLeafX
      nextLeafX += NODE_W + GAP_X
    } else {
      const kids = node.children.map((c) => walk(c, depth + 1, p))
      p.x = (kids[0].x + kids[kids.length - 1].x) / 2
    }
    placed.push(p)
    return p
  }

  walk(root, 0)
  return {
    placed,
    width: Math.max(nextLeafX - GAP_X, NODE_W),
    height: (maxDepth + 1) * (NODE_H + GAP_Y) - GAP_Y,
  }
}

export default function NetworkGraph({ tree }: { tree: TreeNode }) {
  const { placed, width, height } = layout(tree)
  const pad = 20
  return (
    <div className="overflow-x-auto">
      <svg
        width={width + pad * 2}
        height={height + pad * 2}
        viewBox={`${-pad} ${-pad} ${width + pad * 2} ${height + pad * 2}`}
        className="mx-auto block"
      >
        {placed.map(
          (p) =>
            p.parent && (
              <path
                key={`e-${p.node.id}`}
                d={`M ${p.parent.x + NODE_W / 2} ${p.parent.y + NODE_H}
                    C ${p.parent.x + NODE_W / 2} ${p.parent.y + NODE_H + GAP_Y / 2},
                      ${p.x + NODE_W / 2} ${p.y - GAP_Y / 2},
                      ${p.x + NODE_W / 2} ${p.y}`}
                fill="none"
                stroke="#232c4e"
                strokeWidth={2}
              />
            ),
        )}
        {placed.map((p) => {
          const isRoot = !p.parent
          return (
            <g key={p.node.id} transform={`translate(${p.x}, ${p.y})`}>
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={14}
                fill={isRoot ? 'rgba(45,212,191,0.12)' : '#111730'}
                stroke={isRoot ? '#2dd4bf' : '#232c4e'}
                strokeWidth={1.5}
              />
              <text x={12} y={22} fill="#e9edf8" fontSize={13} fontWeight={600} fontFamily="Space Grotesk, sans-serif">
                {p.node.name.length > 16 ? p.node.name.slice(0, 15) + '…' : p.node.name}
              </text>
              <text x={12} y={42} fill={isRoot ? '#2dd4bf' : '#f4b740'} fontSize={12} fontFamily="JetBrains Mono, monospace">
                {isRoot ? `earns ${inr(p.node.direct_earnings)}` : `+${inr(p.node.earned_for_me)} to you`}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
