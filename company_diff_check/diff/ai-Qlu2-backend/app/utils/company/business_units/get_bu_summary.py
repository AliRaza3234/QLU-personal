import json
from qutils.llm.asynchronous import invoke


async def get_business_unit_summary(company, bu):
    SYSTEM_PROMPT = """
    You are a company expert who knows detailed information about the companies product/Business units
        - You will be given a product or a business unit of a company 
        - You will have to provide a summary of what the product is and what influence does it have in market
        - Throw in some more details about the product
        - You will also make sure to return Insutry of the business Unit/product

        Instructions:
            - You will have to return about 5 sentences worth of knowledge about the business unit or product
            - MAKE SURE TO INCLUDE KEY SENTENCES THAT SUMMARISES THE COMPANY BUSINESS UNIT/PRODUCT AND INDUSTRY OF BUSINESS UNIT/PRODUCT
        Output Format:
            - ONLY REUTN JSON OBJECT
            - Keep the keys of JSON object in camel case format.
            - DONT RETURN ANY SENTENCES OUT SIDE OF JSON OBJECT
            - RESPONSE SHOULD START WITH { AND WITH A }
            EXAMPLE:
                - For apple company iphone 
                {
                    "industry": "Consumer Electronics, Telecommunications Equipment, Technology Hardware, Storage & Peripherals",
                    "summary": "The iPhone is Apple's flagship smartphone, renowned for its sleek design, advanced technology, and user-friendly interface
                    Since its launch in 2007, the iPhone has significantly influenced the smartphone market, setting trends in mobile technology and design that competitors 
                    strive to emulate. With features like the App Store, high-quality cameras, and integration with other Apple services, the iPhone has cultivated 
                    a loyal customer base and generated substantial revenue for the company. The device is known for its robust security features, including Face ID and 
                    regular software updates, which enhance user privacy and device longevity. Overall, the iPhone remains a cornerstone of Apple's business strategy, 
                    driving innovation and maintaining its position as a leader in the global smartphone market." 
                }
"""

    query = f"""
        Give me summary and industry for {bu} of {company} company 
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    response = await invoke(
        messages=messages,
        temperature=0.4,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    if response == None:
        return None

    response = json.loads(response)

    return response
