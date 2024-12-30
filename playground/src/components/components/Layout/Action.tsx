import React from "react"

const Action: React.FC = () => {
  return (
    <div className="flex items-center justify-between bg-gray-800 p-2">
      <button className="rounded bg-blue-500 px-4 py-2 text-white">
        Action 1
      </button>
      <button className="rounded bg-green-500 px-4 py-2 text-white">
        Action 2
      </button>
    </div>
  )
}

export default Action
