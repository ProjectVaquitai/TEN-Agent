const AGENT_SERVER_URL = process.env.NEXT_PUBLIC_AGENT_SERVER_URL

export const authService = {
  login: async (email: string, password: string) => {
    console.log(`url: ====> ${AGENT_SERVER_URL}/login`);
    const response = await fetch(`${AGENT_SERVER_URL}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      throw new Error("Login failed")
    }
    const data = await response.json()
    return data
  },

  register: async (name: string, email: string, password: string) => {
    const response = await fetch(`${AGENT_SERVER_URL}/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, email, password }),
    })
    if (!response.ok) {
      throw new Error("Registration failed")
    }
    const data = await response.json()
    return data
  },
}
